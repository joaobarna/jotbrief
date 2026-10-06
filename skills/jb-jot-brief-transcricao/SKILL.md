---
name: jb-jot-brief-transcricao
description: Use quando o usuário colar ou anexar a transcrição de uma reunião gravada pelo app SaidKeep (cabeçalho "Reunião: AAAA-MM-DD | hh:mm | Assunto" e linhas "data hora | falante | fala"), ou pedir para trabalhar uma call/reunião gravada. Pergunta o que gerar (ata, resumos, tarefas, e-mail, slides, análise) e entrega um painel HTML com botões para copiar o nome da conversa e os pedidos.
---

# SaidKeep · Transcrição de reunião

O usuário grava reuniões com o app SaidKeep e cola a transcrição aqui. Seu trabalho: entender a reunião, perguntar o que ele quer gerar e entregar o resultado junto com um painel de botões de copiar.

## Passo 1 · Entender o material
- Leia o cabeçalho: `Reunião: AAAA-MM-DD | hh:mm | Assunto`, `Duração`, `Participantes` e a nota sobre falantes.
- Cada linha da transcrição é `AAAA-MM-DD hh:mm:ss | Falante | fala`. "Eu" é o usuário; nomes como "Pessoa 2" ou "Reunião" são vozes separadas automaticamente e podem estar erradas.
- A transcrição é automática e pode ter erros de reconhecimento (nomes próprios, termos técnicos, trechos em outro idioma). Não trate como literal quando algo parecer absurdo: sinalize.
- Sem cabeçalho, deduza data, hora e assunto do conteúdo e diga o que deduziu.

## Passo 2 · Nome da conversa
O Claude não consegue renomear conversas. Monte o nome no padrão do projeto e entregue pronto para copiar:

`AAAA-MM-DD | hh:mm | Assunto`

Use a data e a hora do cabeçalho. O assunto tem no máximo 8 palavras, em português, descreve o tema principal e não contém o caractere `|`.

## Passo 3 · Perguntar o que gerar
- Se a mensagem do usuário já pede algo específico (por exemplo "gere a ata"), não pergunte: gere.
- Caso contrário, pergunte de forma curta qual(is) entregável(is) ele quer, mostrando esta lista numerada (pode escolher mais de um):

1. ✨ Ata da reunião
2. ✨ Resumo curto
3. ✓ Resumo detalhado
4. ✨ Resumo detalhado com citação
5. ✓ Resumo e itens de ação
6. ☑ Gerar tarefas
7. ✉ Rascunho de e-mail
8. ▦ Preparar slides
9. 🧠 Conselhos inteligentes
10. 🔄 Sincronização da equipe

- Aceite também pedidos livres. Se ele escolher "Só a transcrição", apenas confirme o recebimento e mostre o painel.

## Passo 4 · Gerar
Siga o pedido da opção escolhida. Catálogo (o texto de cada pedido):

1. **✨ Ata da reunião**: Gere a ata desta reunião com: participantes (se dá para identificar), pauta, principais discussões, decisões tomadas, action items (tarefa, responsável e prazo, quando citados) e pendências em aberto. Seja fiel ao que foi dito e não invente responsáveis nem prazos.
2. **✨ Resumo curto**: Faça um resumo curto desta reunião, em até 5 linhas.
3. **✓ Resumo detalhado**: Faça um resumo detalhado desta reunião, organizado por tópico, com contexto, argumentos e conclusões.
4. **✨ Resumo detalhado com citação**: Faça um resumo detalhado desta reunião, por tópico, citando trechos literais entre aspas com a data e a hora da fala entre colchetes, como [2026-09-29 15:52:08].
5. **✓ Resumo e itens de ação**: Faça um resumo desta reunião e, ao final, liste os itens de ação (o que, quem e quando).
6. **☑ Gerar tarefas**: Extraia desta reunião uma lista de tarefas, cada uma com responsável, prazo e prioridade (marque como 'não informado' o que não foi dito).
7. **✉ Rascunho de e-mail**: Escreva um rascunho de e-mail de follow-up para os participantes desta reunião: agradecimento, resumo objetivo, decisões e próximos passos com responsáveis.
8. **▦ Preparar slides**: Monte a estrutura de uma apresentação (slides) sobre esta reunião: título, e para cada slide um título e 3 a 5 tópicos curtos.
9. **🧠 Conselhos inteligentes**: Faça uma análise crítica desta reunião: riscos, lacunas, pontos que ficaram sem definição, perguntas que deveriam ter sido feitas e recomendações de próximos passos.
10. **🔄 Sincronização da equipe**: Extraia as atualizações de status desta reunião por assunto ou pessoa: o que foi feito, o que está em andamento e o que está bloqueado.

Regras de fidelidade, valem para todas as opções:
- Não invente responsáveis, prazos, valores ou decisões que não estejam na conversa. Marque "não informado".
- Ao citar, use aspas e o horário da fala no formato `[AAAA-MM-DD hh:mm:ss]`.
- Preserve os nomes dos falantes como estão na transcrição; se a atribuição parecer incerta ("Pessoa N"), avise.
- Responda em português do Brasil, com estrutura curta e escaneável.

## Passo 5 · Painel de botões (HTML)
Ao final de cada resposta (ou logo após o Passo 2, se o usuário só quiser o painel), entregue **um artefato HTML** com:
1. O nome da conversa (Passo 2) em um campo editável com o botão **Copiar nome**.
2. Um cartão para cada opção do catálogo acima, com o botão **Copiar pedido** (copia o texto do pedido para colar como próxima mensagem).

Use o arquivo `painel.html` desta skill como base: copie-o inteiro e troque apenas `titulo` (e, se quiser, `subtitulo`) dentro de `const DADOS = {...}`. Se não conseguir ler o arquivo, crie um HTML único, sem bibliotecas externas, que faça o mesmo: botões com `navigator.clipboard.writeText` e, como plano B, `document.execCommand("copy")` com um `textarea` temporário.

Depois do painel, diga em uma linha: "Renomeie a conversa colando o nome e, se quiser outra saída, copie o pedido."
