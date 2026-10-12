# Astra-Enem pessoal

Aplicativo pessoal executável para explorar prática adaptativa e organizar o estudo. Interface em português, sem cadastro, com dados locais em SQLite. Não é uma plataforma de correção oficial nem garante 800/900 pontos.

## Iniciar

Requisito: Python 3.12 e acesso ao PyPI na primeira instalação. Em Linux/macOS, na pasta do projeto:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m astra.server
```

Em Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m astra.server
```

No seu computador pessoal, abra o navegador no endereço HTTP de `127.0.0.1`, porta `8000`. O servidor aceita somente conexões locais. No onboarding em nuvem, o fluxo é validado por requisições internas; a interface de onboarding não fornece preview do aplicativo. Para uso pessoal, copie ou baixe o projeto e execute os comandos acima em seu computador.

Outra porta: `python -m astra.server --port 8080`. Encerre com Ctrl+C. O arquivo `.local/astra.sqlite3` preserva as tentativas e o resumo da última análise de redação. A foto não é armazenada nem enviada a provedores externos. Não compartilhe o banco com terceiros. O botão de reinício remove as tentativas e análises locais; faça uma cópia do banco com o servidor parado se desejar um backup.

## O que funciona

- Banco **sintético** de 180 itens: 45 por área. São exercícios didáticos simples, com explicação, não questões oficiais ou uma prova representativa do ENEM. Vários itens de Linguagens/Humanas compartilham estruturas; não devem ser usados para estimar desempenho real.
- Quatro posteriores de θ, atualizados a cada resposta pela TRI 3PL em grade numérica, com média e desvio posterior. `a`, `b` e `c` são parâmetros ilustrativos, não calibrados; não há conversão em nota ENEM.
- Próximo item escolhido por informação esperada, alvo de acerto, cobertura de áreas, lacunas e vencimento de revisões. Itens não se repetem na sessão.
- Pré-requisitos impedem itens avançados dependentes quando o índice local de evidência é menor que 0,65. O índice usa prior Beta(1,1): 50% inicial não é diagnóstico. É uma heurística, não a política de domínio com limites de credibilidade proposta na arquitetura.
- Indicador operacional de carga baseado em lentidão e erros acima do esperado. A versão local compara tempos na mesma área; o ajuste robusto por dificuldade da arquitetura é uma evolução pendente. Inatividade visível também pode confundir esse indicador. Confiança declarada é registrada, sem alterar θ.
- Revisões sugeridas por uma curva exponencial ilustrativa de retenção, com estabilidade ajustada por sucesso/falha. Não implementa FSRS nem a calibração prospectiva descrita na arquitetura.
- Redação: contagem e checklist estrutural local. Todas as cinco notas ficam **não avaliadas**. Os três agentes estão especificados na arquitetura, sem chamadas de IA.
- Caderno: upload com limite de 4,5 MB, prévia e transcrição manual, checklist de revisão. Sem OCR ou diagnóstico automático; a classificação permanece **indeterminada**.

O banco é finito. Se os pré-requisitos não forem atingidos, a sessão pode terminar antes dos 180 itens; a tela identifica esse caso. Uma versão de uso educacional continuado precisa de recuperação com novos itens e revisão humana, sem remover a barreira silenciosamente. Para experimentar outra sessão nesta versão, use o reinício após revisar as bases.

## Arquitetura e motor

Leia [docs/ARQUITETURA.md](docs/ARQUITETURA.md) para os cinco eixos: prompts de sistema e consolidação, visão computacional, equações de fadiga/espaçamento, nós/arestas Neo4j e GraphQL, e TRI. Neo4j, GNN, APIs de modelos e processamento visual são **propostas**, não dependências executadas neste aplicativo. O modelo numérico interpretável usa NumPy; adicionar uma GNN sem dados e validação não justificaria maior precisão.

Código: `astra/bank.py` (itens), `astra/engine.py` (TRI/seleção), `astra/server.py` (API/SQLite), `static/index.html` (interface).

Simulação reproduzível com banco de 180 itens:

```bash
.venv/bin/python -m astra.simulate --steps 180 --seed 42
```

A saída JSONL mostra θ, desvio posterior e o ID seguinte a cada iteração. Com a semente 42, a barreira interrompe a sequência após 171 respostas, deixando nove itens inelegíveis. A suíte também verifica uma sequência adaptativa de 180 acertos, que visita todo o banco sem repetição.

Para alimentar respostas reais, use `--responses respostas.json`, com uma lista de objetos `{"question_id":"ID recomendado","option":0}` (alternativas 0 a 4). A ordem precisa acompanhar as recomendações; a API da aplicação é a forma interativa mais simples. O ID inicial e os próximos IDs são obtidos em `/api/state` e na saída JSONL.

## Validar

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Os testes cobrem banco, estabilidade numérica, atualização por área, barreira, sequência completa, persistência, concorrência, entradas inválidas, chamadas HTTP e ausência de avaliações inventadas. A aplicação foi iniciada e validada com requisições funcionais no ambiente atual. Nenhuma restauração em nova tarefa ou publicação da configuração é pressuposta.

## Limites operacionais

Este é um aplicativo **pessoal local**, não um serviço pronto para publicação comercial. O servidor Python usa bloqueio local e transações SQLite, valida entrada, restringe Host/Origin, não habilita CORS e não expõe respostas corretas antes da tentativa. Expor pela Internet exige outro servidor, autenticação, TLS, isolamento por usuário, migrações e política de dados. Não altere o bind para endereço público sem implementar esses requisitos.

Redação não usa TRI. As cinco competências oficiais exigem uma rubrica versionada e avaliação apropriada. Não se deve confundir erro de cálculo com diagnóstico de desatenção, nem θ sintético com nota oficial. O modelo de IA disponível deve ser verificado no provedor antes de configurar a proposta dos três agentes; o nome pedido pelo usuário não comprova disponibilidade de API.
