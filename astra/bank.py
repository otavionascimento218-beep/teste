"""Deterministic synthetic bank. Item parameters are illustrative, not calibrated."""
from dataclasses import asdict, dataclass
import math
import random

AREAS = ['Matemática', 'Natureza', 'Linguagens', 'Humanas']
CONCEPTS = {
    'potencias': ('Propriedades das potências', 0, []),
    'geometria': ('Área e proporcionalidade', 0, []),
    'logaritmos': ('Logaritmos e função exponencial', 0, ['potencias']),
    'mol': ('Quantidade de matéria', 1, []),
    'estequiometria': ('Estequiometria', 1, ['mol']),
    'cinematica': ('Velocidade média', 1, []),
    'leitura': ('Informação explícita', 2, []),
    'argumentacao': ('Argumentação e finalidade', 2, ['leitura']),
    'generos': ('Gêneros textuais', 2, ['leitura']),
    'fontes': ('Análise de fontes históricas', 3, []),
    'cidadania': ('Participação e cidadania', 3, ['fontes']),
    'escala': ('Escala cartográfica', 3, []),
}

@dataclass(frozen=True)
class Item:
    id: str
    area_index: int
    concept: str
    difficulty: float
    a: float
    c: float
    stem: str
    options: tuple[str, ...]
    answer: int
    explanation: str

    def public(self):
        value = asdict(self)
        value.pop('answer')
        value.pop('explanation')
        value['area'] = AREAS[self.area_index]
        value['concept_label'] = CONCEPTS[self.concept][0]
        return value

def numeric_options(correct, rng):
    values = {float(correct)}
    for delta in [1, -1, 2, -2, 3, 4, 5]:
        values.add(float(correct + delta))
        if len(values) == 5:
            break
    values = list(sorted(values))
    rng.shuffle(values)
    render = lambda v: f'{v:g}'
    return tuple(map(render, values)), values.index(float(correct))

def make_bank():
    items = []
    rng = random.Random(20261012)
    for area in range(4):
        for n in range(45):
            family, k = n % 3, n // 3 + 1
            concept = list(CONCEPTS)[area * 3 + family]
            if area == 0:
                if family == 0:
                    base, exponent = 2 + k % 3, 1 + k // 3
                    correct = base ** (exponent + 1)
                    stem = f'Calcule {base}^{exponent} × {base}¹.'
                    explanation = f'Mesma base: some os expoentes. {base}^{exponent + 1} = {correct}.'
                elif family == 1:
                    w, h = k + 3, k + 1
                    correct = w * h
                    stem = f'Um terreno retangular tem lados {w} m e {h} m. Qual é sua área em m²?'
                    explanation = f'Área = base × altura = {w} × {h} = {correct} m².'
                else:
                    base = 2 + k % 3
                    correct = k
                    stem = f'Uma população obedece P(t) = {base}^t. Se P(t) = {base**k}, determine t.'
                    explanation = f'{base**k} = {base}^{k}; portanto t = log na base {base} de {base**k} = {k}.'
            elif area == 1:
                if family == 0:
                    correct = k
                    stem = f'Uma amostra de água tem massa {18*k} g. Com M(H₂O) = 18 g/mol, quantos mols há?'
                    explanation = f'n = m/M = {18*k}/18 = {k} mol.'
                elif family == 1:
                    correct = 2*k
                    stem = f'Na reação 2 H₂ + O₂ → 2 H₂O, {k} mol de O₂ reagem com H₂ em excesso. Quantos mols de H₂O se formam?'
                    explanation = f'A proporção O₂:H₂O é 1:2. Logo {k} × 2 = {correct} mol de água.'
                else:
                    correct = k + 5
                    stem = f'Um móvel percorre {(k+5)*3} km em 3 h. Qual a velocidade média em km/h?'
                    explanation = f'v = Δs/Δt = {(k+5)*3}/3 = {correct} km/h.'
            elif area == 2:
                if family == 0:
                    correct = k + 7
                    stem = f'Leia: “A biblioteca abriu às 8h e recebeu {correct} visitantes pela manhã.” Quantos visitantes são explicitamente mencionados?'
                    explanation = f'O texto informa diretamente {correct} visitantes; o horário não responde à pergunta.'
                elif family == 1:
                    stem = f'Campanha {k}: “Use transporte coletivo: menos carros reduzem emissões.” Qual trecho funciona como justificativa?'
                    texts = ['Menos carros reduzem emissões', 'Use transporte coletivo', 'Campanha', 'O número da campanha', 'Nenhum trecho']
                    rng.shuffle(texts)
                    options, answer = tuple(texts), texts.index('Menos carros reduzem emissões')
                    explanation = 'A redução de emissões é a razão apresentada para apoiar a recomendação.'
                else:
                    stem = f'Aviso {k}: “A reunião ocorrerá no dia {k}, às 14h, na sala 2.” Qual é sua finalidade predominante?'
                    texts = ['Informar local e horário', 'Narrar uma aventura', 'Definir uma teoria', 'Vender um produto', 'Descrever um sonho']
                    rng.shuffle(texts)
                    options, answer = tuple(texts), texts.index('Informar local e horário')
                    explanation = 'O aviso comunica informações práticas para orientar os participantes.'
            else:
                if family == 0:
                    stem = f'Arquivo {k}: um diário pessoal relata um acontecimento histórico. Como usá-lo de forma crítica?'
                    texts = ['Contextualizar autoria e comparar com outras fontes', 'Tratá-lo como relato neutro absoluto', 'Ignorar a data de produção', 'Supor que representa toda a população', 'Descartar todo relato pessoal']
                    rng.shuffle(texts)
                    options, answer = tuple(texts), texts.index('Contextualizar autoria e comparar com outras fontes')
                    explanation = 'Uma fonte tem perspectiva situada; contexto e comparação ajudam a avaliar seu alcance.'
                elif family == 1:
                    stem = f'Caso {k}: moradores discutem prioridades de investimento em uma audiência pública. Isso exemplifica principalmente:'
                    texts = ['Participação cidadã nas decisões públicas', 'Proibição de debate', 'Substituição de toda a legislação', 'Fim da representação política', 'Privatização obrigatória']
                    rng.shuffle(texts)
                    options, answer = tuple(texts), texts.index('Participação cidadã nas decisões públicas')
                    explanation = 'A audiência é um espaço de participação; não elimina outras instituições ou obrigações legais.'
                else:
                    correct = k
                    stem = f'Em um mapa de escala 1:100.000, a distância é {k} cm. Qual a distância real em km?'
                    explanation = f'Cada cm corresponde a 100.000 cm = 1 km. Logo {k} cm representam {k} km.'
            if area < 2 or (area == 2 and family == 0) or (area == 3 and family == 2):
                options, answer = numeric_options(correct, rng)
            # Difficulty is simulated independently of item content: explicitly uncalibrated.
            b = -2.0 + 4.0 * (k - 1) / 14
            items.append(Item(f'{area+1}-{n+1:03}', area, concept, b, 1.0 + .2*(family+1), .2,
                              stem, options, answer, explanation))
    return items

BANK = make_bank()
BY_ID = {q.id: q for q in BANK}
