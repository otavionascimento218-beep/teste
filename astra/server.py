"""Local-only personal HTTP application. No cloud AI or official score claims."""
import argparse
from contextlib import contextmanager
import base64
import binascii
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .bank import BANK, BY_ID, CONCEPTS
from .engine import probability, recommendations, review_schedule

ROOT = Path(__file__).resolve().parent.parent
MAX_BODY = 7_000_000

class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS responses (
                question_id TEXT PRIMARY KEY, option INTEGER NOT NULL, correct INTEGER NOT NULL,
                reaction_seconds REAL NOT NULL, confidence REAL NOT NULL,
                predicted_probability REAL NOT NULL, created_at REAL NOT NULL)''')
            db.execute('CREATE TABLE IF NOT EXISTS artifacts (kind TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def history(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM responses ORDER BY created_at, rowid')]

    def state(self):
        with self.lock:
            history = self.history()
            item, theta, sd, levels, f = recommendations(history)
            with self.connect() as db:
                row = db.execute("SELECT payload FROM artifacts WHERE kind='essay'").fetchone()
            concepts = [{'id': k, 'label': v[0], 'mastery': levels[k],
                         'blocked': any(levels[p] < .65 for p in v[2]),
                         'prerequisites': v[2], 'area_index': v[1]} for k,v in CONCEPTS.items()]
            public = item.public() if item else None
            if public:
                public['predicted_probability'] = float(probability(item, theta[item.area_index]))
            return {'student': {'id': 'personal', 'name': 'Explorador',
                                'theta': theta.tolist(), 'uncertainty': sd.tolist(), 'fatigue': f},
                    'answered': len(history), 'total': len(BANK), 'next_question': public,
                    'recent': list(reversed(history[-8:])), 'concepts': concepts,
                    'reviews': review_schedule(history), 'essay': json.loads(row[0]) if row else None,
                    'limitations': ['Banco sintético e parâmetros não calibrados.',
                                    'θ não equivale à nota oficial do ENEM.',
                                    'Fadiga é um indicador heurístico, não uma medição clínica.']}

    def answer(self, data):
        question_id = data.get('question_id')
        if not isinstance(question_id, str) or question_id not in BY_ID:
            raise ValueError('Questão inválida.')
        option = data.get('option')
        if type(option) is not int or not 0 <= option < 5:
            raise ValueError('Escolha uma alternativa entre 0 e 4.')
        reaction = finite_number(data.get('reaction_seconds'), 'tempo', 0, 86400)
        confidence = finite_number(data.get('confidence', .5), 'confiança', 0, 1)
        with self.lock:
            history = self.history()
            next_item, theta, *_ = recommendations(history)
            if next_item is None or next_item.id != question_id:
                raise Conflict('A questão já foi respondida ou a recomendação mudou. Atualize a tela.')
            item = BY_ID[question_id]
            correct = option == item.answer
            p = float(probability(item, theta[item.area_index]))
            with self.connect() as db:
                db.execute('INSERT INTO responses VALUES (?,?,?,?,?,?,?)',
                           (question_id, option, int(correct), reaction, confidence, p, time.time()))
            return {'correct': correct, 'explanation': item.explanation, 'state': self.state()}

    def save_artifact(self, kind, payload):
        with self.lock, self.connect() as db:
            db.execute('INSERT OR REPLACE INTO artifacts VALUES (?,?)',
                       (kind, json.dumps(payload, ensure_ascii=False, allow_nan=False)))

    def reset(self):
        with self.lock, self.connect() as db:
            db.execute('DELETE FROM responses')
            db.execute('DELETE FROM artifacts')
        return self.state()

class Conflict(ValueError):
    pass

def finite_number(value, name, low, high):
    if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name}: informe um número entre {low} e {high}.')
    return float(value)

def text_field(data, key, maximum, required=True):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f'Campo {key}: texto obrigatório, com até {maximum} caracteres.' if required
                         else f'Campo {key}: use até {maximum} caracteres.')
    return value.strip()

def inspect_essay(data):
    text = text_field(data, 'text', 20000)
    theme = text_field(data, 'theme', 500)
    paragraphs = [p for p in re.split(r'\n\s*\n|\n', text) if p.strip()]
    words = re.findall(r'\b[\wÀ-ÿ]+\b', text)
    feedback = [f'Texto recebido: {len(words)} palavras e {len(paragraphs)} parágrafos. '
                'Essas contagens não determinam nota nem equivalem ao número de linhas da folha oficial.',
                'Verifique a tese, o encadeamento das justificativas e a pertinência ao tema: ' + theme,
                'Revise a proposta de intervenção: ação, agente, meio, finalidade e detalhamento, respeitando os direitos humanos.',
                'Repertórios e citações precisam ser conferidos em fontes confiáveis; esta análise não verifica sua autenticidade.']
    if len(paragraphs) == 1:
        feedback.append('O texto tem um único parágrafo. Examine se a organização facilita acompanhar a argumentação.')
    labels = ['Norma escrita formal', 'Tema, gênero e repertório', 'Seleção e organização dos argumentos',
              'Coesão e mecanismos linguísticos', 'Proposta de intervenção']
    return {'status': 'needs_human_review', 'word_count': len(words), 'paragraph_count': len(paragraphs),
            'theme': theme, 'feedback': feedback, 'total': None,
            'competencies': [{'id': n+1, 'label': label, 'score': None, 'status': 'Não avaliada por IA'}
                             for n,label in enumerate(labels)],
            'agents': [{'name': name, 'status': 'Especificado; integração não configurada'} for name in
                       ['Norma culta', 'Repertório e argumentação', 'Auditoria das competências']],
            'disclaimer': 'Análise estrutural local. Sem nota automática e sem chamada a modelos externos.'}

def inspect_work(data):
    problem = text_field(data, 'problem', 4000)
    transcription = text_field(data, 'work_text', 12000, required=False)
    image = data.get('image_base64', '')
    if not isinstance(image, str):
        raise ValueError('Imagem inválida.')
    if not image and not transcription:
        raise ValueError('Envie uma foto ou uma transcrição.')
    if image:
        match = re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\r\n]+)', image)
        if not match:
            raise ValueError('Formato aceito: PNG, JPEG ou WebP em base64.')
        try:
            content = base64.b64decode(match[2], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError('Imagem base64 inválida.') from exc
        if len(content) > 4_500_000 or len(content) < 12:
            raise ValueError('Imagem deve ter no máximo 4,5 MB e não estar vazia.')
        signatures = {'png': content.startswith(b'\x89PNG\r\n\x1a\n'),
                      'jpeg': content.startswith(b'\xff\xd8\xff'),
                      'webp': content.startswith(b'RIFF') and content[8:12] == b'WEBP'}
        if not signatures[match[1]]:
            raise ValueError('A assinatura da imagem não corresponde ao formato informado.')
        # No decoding or storage: preserve personal images, avoid pretending to perform OCR.
    return {'status': 'needs_transcription_review', 'classification': 'indeterminate',
            'image_received': bool(image), 'transcription_received': bool(transcription),
            'problem': problem,
            'feedback': [('Foto recebida sem processamento por visão computacional; ela não foi armazenada.'
                          if image else 'Revisão baseada na transcrição manual; nenhuma foto foi enviada.'),
                         'Confirme a transcrição linha por linha, incluindo unidades, sinais e expoentes.',
                         'Compare a fórmula e as relações físicas com o enunciado. Uma regra inadequada sugere erro conceitual.',
                         'Se a regra estiver adequada, recalcule cada operação. Um resultado isolado divergente sugere erro de cálculo; não prova desatenção.',
                         'Sem análise validada das etapas, o diagnóstico permanece indeterminado.']}

def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'AstraPersonal/0.1'

        def valid_host(self):
            return self.headers.get('Host', '') in self.server.allowed_hosts

        def send(self, status, payload, content_type='application/json; charset=utf-8'):
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode() if isinstance(payload, (dict,list)) else payload
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {'error': 'Host não autorizado. Use localhost ou 127.0.0.1.'})
            route = urlsplit(self.path).path
            if route == '/api/state':
                return self.send(200, store.state())
            if route == '/health':
                return self.send(200, {'status': 'ok', 'items': len(BANK), 'mode': 'local-synthetic'})
            if route in ('/', '/index.html'):
                return self.send(200, (ROOT/'static/index.html').read_bytes(), 'text/html; charset=utf-8')
            if route == '/docs':
                return self.send(200, (ROOT/'docs/ARQUITETURA.md').read_bytes(), 'text/plain; charset=utf-8')
            return self.send(404, {'error': 'Rota inexistente.'})

        def do_POST(self):
            if not self.valid_host():
                return self.send(403, {'error': 'Host não autorizado.'})
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.send(403, {'error': 'Origem não autorizada.'})
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                return self.send(403, {'error': 'Requisição externa não autorizada.'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error': 'Use application/json.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 1 or length > MAX_BODY:
                    return self.send(413, {'error': 'Tamanho de requisição inválido (máximo 7 MB).'})
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError('Corpo incompleto.')
                data = json.loads(raw, parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Número inválido.')))
                if not isinstance(data, dict):
                    raise ValueError('Envie um objeto JSON.')
                route = urlsplit(self.path).path
                if route == '/api/answer':
                    payload = store.answer(data)
                elif route == '/api/reset':
                    payload = store.reset()
                elif route == '/api/essay':
                    payload = inspect_essay(data)
                    store.save_artifact('essay', payload)
                elif route == '/api/vision':
                    payload = inspect_work(data)
                else:
                    return self.send(404, {'error': 'Rota inexistente.'})
                return self.send(200, payload)
            except Conflict as exc:
                return self.send(409, {'error': str(exc)})
            except (ValueError, UnicodeDecodeError) as exc:
                return self.send(400, {'error': str(exc)})
            except sqlite3.Error:
                return self.send(500, {'error': 'Falha no armazenamento local.'})

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, format, *args):
            # Never log user-submitted bodies or essay content.
            return
    return Handler

def main():
    parser = argparse.ArgumentParser(description='Astra-Enem pessoal: acesso local, sem autenticação remota.')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--db', default=os.environ.get('ASTRA_DB_PATH', str(ROOT/'.local/astra.sqlite3')))
    args = parser.parse_args()
    store = Store(args.db)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(store))
    server.daemon_threads = True
    port = server.server_address[1]
    server.allowed_hosts = {f'localhost:{port}', f'127.0.0.1:{port}'}
    print(f'Astra-Enem iniciado na porta {port}; banco sintético de {len(BANK)} questões.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
