#!/usr/bin/env python3
"""
Gera dados sintéticos de callcenter financeiro PT-BR para a FinanceiraX S.A.
100 conversas: 10 categorias x 10 conversas (5 reclamacoes + 5 elogios)
Produtos: Seguro, Cartao de Credito, Emprestimos, Credito Especial, Consorcio
"""
import json
import uuid
import random
import os
from datetime import datetime, timedelta

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'sample_processed_data.json')

CLIENTES = [
    "Ana Silva", "Bruno Santos", "Carla Oliveira", "Diego Ferreira", "Elena Costa",
    "Fabio Lima", "Gabriela Martins", "Henrique Pereira", "Isabela Rodrigues", "Joao Alves",
    "Karina Souza", "Lucas Carvalho", "Marina Gomes", "Nelson Ribeiro", "Olivia Mendes",
    "Paulo Barbosa", "Quesia Nunes", "Rafael Pinto", "Sabrina Freitas", "Thiago Azevedo"
]

ATENDENTES = ["Amanda", "Carlos", "Denise", "Eduardo", "Fernanda",
              "Gustavo", "Helena", "Igor", "Juliana", "Kleber"]


def pnome(nome):
    return nome.split()[0]


def gerar_datas(duracao_min=8, duracao_max=22):
    base = datetime(2024, 9, 1) + timedelta(days=random.randint(0, 365))
    hora = random.randint(8, 18)
    minuto = random.choice([0, 15, 30, 45])
    start = base.replace(hour=hora, minute=minuto, second=0)
    duracao = random.randint(duracao_min, duracao_max)
    end = start + timedelta(minutes=duracao)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")


def entry(content, summary, satisfied, sentiment, topic, key_phrases, complaint, mined_topic):
    start, end = gerar_datas()
    return {
        "ConversationId": str(uuid.uuid4()),
        "EndTime": end,
        "StartTime": start,
        "Content": content.strip(),
        "summary": summary,
        "satisfied": satisfied,
        "sentiment": sentiment,
        "topic": topic,
        "key_phrases": key_phrases,
        "complaint": complaint,
        "mined_topic": mined_topic
    }


def prot():
    return random.randint(100000, 999999)


# ============================================================
# 1. SEGURO — CONTRATACAO E CANCELAMENTO
# ============================================================

def seg_contrat_recl(c, a, contrato, valor):
    p = prot()
    return entry(
        f"Boa tarde, tudo bem? Ola, {pnome(c)}, meu nome e {a}, atendente da FinanceiraX S.A. Em que posso ajudar? "
        f"Liguei para cancelar meu seguro de vida, contrato {contrato}, mas ja tentei duas vezes e continuam me cobrando. "
        f"Entendo sua insatisfacao, {pnome(c)}. Vou verificar o contrato agora. Um momento, por favor. "
        f"Encontrei o contrato. Havia um erro no processamento do cancelamento anterior e a cobranca continuou. "
        f"Isso e inadmissivel! Paguei R$ {valor:,.0f} indevidamente no mes passado. "
        f"Tem razao, {pnome(c)}. Peco desculpas. Vou registrar o cancelamento definitivo agora e solicitar o estorno de R$ {valor:,.0f} em ate 10 dias uteis. "
        f"Da ultima vez prometeram isso e nao cumpriram. "
        f"Compreendo sua desconfianca. Desta vez gero um protocolo prioritario: {p}. Enviarei confirmacao por e-mail com o prazo. "
        f"Se cobrar novamente vou acionar o Procon. "
        f"Completamente justificado, {pnome(c)}. Garanto que o cancelamento e o estorno serao efetuados. Algo mais? "
        f"Nao. Obrigada. "
        f"Obrigada pelo contato. Tenha um bom dia.",
        f"Cliente solicitou cancelamento do seguro de vida {contrato} e relatou cobranca indevida de R$ {valor:,.0f} apos tentativas anteriores. Agente registrou cancelamento definitivo com protocolo {p} e solicitou estorno.",
        "No", "Negative",
        "Cancelamento com cobranca indevida",
        "cancelamento seguro, cobranca indevida, estorno, apolice, protocolo prioritario, seguro de vida, tentativa cancelamento, prazo estorno, Procon, insatisfacao",
        "cancelamento negado",
        "Seguro — Contratacao e Cancelamento"
    )


def seg_contrat_elogio(c, a, contrato, valor):
    premio = round(valor * 0.0012, 2)
    return entry(
        f"Boa tarde! Ola, {pnome(c)}, aqui e {a} da FinanceiraX S.A. Em que posso ajudar? "
        f"Quero contratar um seguro residencial. Minha casa e avaliada em R$ {valor:,.0f}. "
        f"Excelente, {pnome(c)}! Temos tres planos: Basico com cobertura incendio e roubo, Intermediario com danos eletricos incluidos, e o Premium com cobertura total. "
        f"Para um imovel de R$ {valor:,.0f} o Intermediario e o mais indicado. "
        f"Qual o valor do Intermediario? "
        f"O premio mensal seria de R$ {premio:,.2f} com franquia de R$ 500,00. "
        f"Gostei! Podemos contratar agora? "
        f"Sim! Vou fazer o cadastro agora mesmo. Preciso do seu CPF e endereco do imovel. "
        f"Perfeito. Contrato gerado: {contrato}. A apolice chegara no seu e-mail em ate 2 dias uteis. "
        f"Otimo! Adorei a rapidez. Obrigada, {a}! "
        f"Fico feliz, {pnome(c)}! A FinanceiraX agradece sua confianca. Algo mais? "
        f"Nao, foi excelente! Tenha um bom dia. "
        f"Igualmente! Ate mais.",
        f"Cliente contratou seguro residencial plano Intermediario com premio mensal de R$ {premio:,.2f}. Contrato {contrato} gerado e apolice enviada por e-mail em ate 2 dias uteis.",
        "Yes", "Positive",
        "Contratacao seguro residencial",
        "seguro residencial, plano intermediario, premio mensal, franquia, apolice, contratacao, cobertura incendio, cobertura roubo, danos eletricos, cadastro",
        "",
        "Seguro — Contratacao e Cancelamento"
    )


# ============================================================
# 2. SEGURO — SINISTROS E INDENIZACOES
# ============================================================

def seg_sinistro_recl(c, a, contrato, valor):
    p = prot()
    dias = random.randint(35, 55)
    return entry(
        f"Bom dia. Bom dia, {pnome(c)}, aqui e {a} da FinanceiraX S.A. Em que posso ajudar? "
        f"Abri um sinistro ha {dias} dias e ate agora nada foi resolvido. O protocolo e {p}. "
        f"Entendo, {pnome(c)}. Vou consultar o protocolo {p} imediatamente. "
        f"O sinistro esta em analise tecnica. A vistoria foi realizada ha 20 dias. "
        f"E o que estao fazendo ha 20 dias? Preciso de R$ {valor:,.0f} para conserto urgente. "
        f"Compreendo a urgencia, {pnome(c)}. A analise esta pendente de laudo. Vou escalar para equipe tecnica com urgencia. "
        f"Ja escalaram tres vezes! Isso e uma falta de respeito. "
        f"Tem razao. Peco sinceras desculpas. Vou registrar reclamacao formal e solicitar posicionamento em 48 horas uteis. "
        f"48 horas! Ja faz quase dois meses! "
        f"Entendo completamente a frustracao. Vou contatar o gerente tecnico agora. Caso nao haja retorno, ligue e peca escalada para ouvidoria. "
        f"Vou fazer isso sim. Que atendimento pessimo. "
        f"Lamentamos muito, {pnome(c)}. A situacao sera resolvida. Tenha um bom dia. "
        f"Espero que sim. Tchau.",
        f"Cliente relata sinistro ha {dias} dias sem resolucao para conserto no valor de R$ {valor:,.0f}. Agente escalou caso para equipe tecnica e registrou reclamacao formal com prazo de 48 horas.",
        "No", "Negative",
        f"Sinistro pendente {dias} dias sem resolucao",
        "sinistro pendente, prazo expirado, laudo tecnico, vistoria realizada, escalada reclamacao, indenizacao atrasada, ouvidoria, analise tecnica, urgencia, protocolo",
        "sinistro sem resolucao",
        "Seguro — Sinistros e Indenizacoes"
    )


def seg_sinistro_elogio(c, a, contrato, valor):
    p = prot()
    dias = random.randint(3, 7)
    return entry(
        f"Boa tarde. Boa tarde, {pnome(c)}, meu nome e {a} da FinanceiraX S.A. Como posso ajudar? "
        f"Liguei para verificar meu sinistro, protocolo {p}. "
        f"Claro! Otima noticia: o sinistro foi aprovado e o pagamento de R$ {valor:,.0f} foi processado hoje. "
        f"Serio? Abri o sinistro ha apenas {dias} dias! "
        f"Sim! Nossa equipe priorizou o caso. O valor ja esta disponivel na sua conta cadastrada. "
        f"Fantastico! Fiquei com medo que fosse demorar muito. "
        f"Entendemos a urgencia, {pnome(c)}, e trabalhamos para resolver o mais rapido possivel. "
        f"Muito obrigado, {a}! Fiquei muito satisfeito com a agilidade. "
        f"Fico feliz que tenha ficado satisfeito! A FinanceiraX esta sempre aqui. Algo mais? "
        f"Nao, esta otimo. Voces sao excelentes! "
        f"Obrigado pelo elogio! A FinanceiraX agradece sua confianca. Tenha um excelente dia.",
        f"Sinistro {p} aprovado e valor de R$ {valor:,.0f} processado em apenas {dias} dias. Cliente muito satisfeito com a agilidade da FinanceiraX.",
        "Yes", "Positive",
        "Sinistro aprovado rapidamente",
        "sinistro aprovado, pagamento processado, agilidade, indenizacao, prazo rapido, aprovacao sinistro, conta cadastrada, satisfacao, FinanceiraX, urgencia atendida",
        "",
        "Seguro — Sinistros e Indenizacoes"
    )


# ============================================================
# 3. CARTAO DE CREDITO — FATURA E PAGAMENTO
# ============================================================

def cartao_fatura_recl(c, a, contrato, valor):
    p = prot()
    return entry(
        f"Alo. Boa tarde, {pnome(c)}, meu nome e {a} da FinanceiraX S.A. Em que posso ajudar? "
        f"Tem uma cobranca de R$ {valor:,.0f} na minha fatura que nao reconheco. Nao fiz essa compra. "
        f"Entendo, {pnome(c)}. Vou verificar as transacoes. Um momento. "
        f"Localizei a transacao. Aparece como compra parcelada em eletronicos. "
        f"Definitivamente nao fui eu. Meu cartao estava comigo o tempo todo. "
        f"Compreendo. Precisamos abrir uma contestacao formal. Protocolo {p}. Bloquearei o cartao preventivamente. "
        f"Terei que ficar sem cartao? "
        f"Infelizmente sim, por seguranca enquanto investigamos. Enviaremos um novo em ate 5 dias uteis. "
        f"Cinco dias sem cartao! E a anuidade que estao me cobrando sem ter contratado? "
        f"Vou verificar a anuidade tambem. Caso nao conste no contrato, abriremos contestacao separada. "
        f"Nao contratei nada disso! Quero um gerente. "
        f"Vou registrar solicitacao de contato gerencial em ate 24 horas. Protocolo {p}. "
        f"Aguardo. Tchau. "
        f"Obrigado pelo contato. Tenha um bom dia.",
        f"Cliente contestou transacao suspeita de R$ {valor:,.0f} na fatura e cobranças de anuidade nao contratada. Agente bloqueou cartao, abriu protocolo {p} e registrou contestacao.",
        "No", "Negative",
        "Contestacao de cobranca indevida",
        "contestacao fatura, cobranca indevida, transacao suspeita, bloqueio preventivo, anuidade nao contratada, prazo 30 dias, fraude, estorno, protocolo, novo cartao",
        "cobranca indevida",
        "Cartao de Credito — Fatura e Pagamento"
    )


def cartao_fatura_elogio(c, a, contrato, valor):
    parcelas = random.choice([6, 10, 12])
    entrada = round(valor * 0.1, 2)
    return entry(
        f"Boa tarde! Boa tarde, {pnome(c)}, meu nome e {a} da FinanceiraX S.A. Como posso ajudar? "
        f"Tenho uma fatura de R$ {valor:,.0f} e quero saber se consigo parcelar no cartao. "
        f"Claro, {pnome(c)}! Deixa eu verificar as opcoes. Temos {parcelas} parcelas com juros de 2,5% ao mes, "
        f"ou {parcelas//2} parcelas sem juros com entrada de R$ {entrada:,.2f}. "
        f"O parcelamento sem juros com entrada e melhor! "
        f"Excelente escolha, {pnome(c)}! Posso registrar agora mesmo. A entrada deve ser paga ate o vencimento. "
        f"Combinado. Pode registrar. "
        f"Pronto! Parcelamento efetuado com sucesso. A proxima fatura ja vira com a primeira parcela. "
        f"Perfeito! Voces facilitaram muito. Obrigado, {a}! "
        f"Fico feliz em ajudar, {pnome(c)}! A FinanceiraX preza pelo seu conforto. Precisa de mais alguma coisa? "
        f"Nao, foi tudo otimo! Tenha um bom dia. "
        f"Igualmente! Ate mais.",
        f"Cliente negociou parcelamento de fatura de R$ {valor:,.0f} em {parcelas//2} parcelas sem juros com entrada de R$ {entrada:,.2f}. Acordado com sucesso.",
        "Yes", "Positive",
        "Parcelamento de fatura negociado",
        "parcelamento fatura, sem juros, entrada, negociacao, fatura, cartao credito, parcelas, vencimento, opcoes pagamento, acordo",
        "",
        "Cartao de Credito — Fatura e Pagamento"
    )


# ============================================================
# 4. CARTAO DE CREDITO — BLOQUEIO E CONTESTACAO
# ============================================================

def cartao_bloqueio_recl(c, a, contrato, valor):
    p = prot()
    return entry(
        f"Boa tarde. Boa tarde, {pnome(c)}, aqui e {a} da FinanceiraX. Em que posso ajudar? "
        f"Meu cartao {contrato} foi bloqueado sem motivo! Estava tentando pagar R$ {valor:,.0f} e foi recusado. "
        f"Entendo, {pnome(c)}. Vou verificar o motivo do bloqueio. Um momento. "
        f"O bloqueio foi realizado pelo sistema antifraude que detectou uso incomum. "
        f"Que uso incomum? Sou eu quem usa meu cartao! Nunca fui bloqueado antes. "
        f"Compreendo sua frustracao. Para desbloquear preciso confirmar alguns dados. Tentou pelo app? "
        f"Sim, tentei e nao funcionou! Por isso liguei. "
        f"Peco desculpas pelo transtorno. Farei a verificacao por aqui. Pode confirmar data de nascimento e CEP? "
        f"Sim, tenho tudo aqui. "
        f"Verificado. Desbloqueio efetuado! Protocolo {p}. Mas o sistema pode bloquear novamente em padrao incomum. "
        f"E nao ha como sinalizar que sou eu? Isso e absurdo! "
        f"Posso registrar preferencia de contato antes do proximo bloqueio. Assim te avisamos antes. "
        f"Pelo menos isso. Registre. Mas o app deveria funcionar! "
        f"Registrado, {pnome(c)}. Encaminharei feedback sobre o app. Protocolo {p}. Bom dia.",
        f"Cartao {contrato} bloqueado por antifraude durante compra de R$ {valor:,.0f}. Cliente frustrado com processo de desbloqueio e falha no app. Agente desbloqueou apos verificacao com protocolo {p}.",
        "No", "Negative",
        "Bloqueio indevido cartao credito",
        "bloqueio cartao, antifraude, desbloqueio, verificacao identidade, app falhou, sistema antifraude, padrao incomum, protocolo desbloqueio, frustracao, compra recusada",
        "bloqueio indevido",
        "Cartao de Credito — Bloqueio e Contestacao"
    )


def cartao_bloqueio_elogio(c, a, contrato, valor):
    p = prot()
    hora = random.randint(2, 5)
    return entry(
        f"Boa tarde! Boa tarde, {pnome(c)}, meu nome e {a} da FinanceiraX. Como posso ajudar? "
        f"Recebi um SMS dizendo que meu cartao {contrato} foi bloqueado por suspeita de fraude. Nao reconheco uma compra de R$ {valor:,.0f}. "
        f"Obrigado por ligar, {pnome(c)}! Fizemos o bloqueio preventivo para te proteger. Vou confirmar a transacao. "
        f"Certo, agradeco a rapidez do SMS. "
        f"A transacao de R$ {valor:,.0f} foi tentada em outro estado as {hora}h da manha. Voce confirma que nao foi voce? "
        f"Com certeza! Estava dormindo. "
        f"Perfeito. Contestacao aberta, protocolo {p}. O valor sera estornado em ate 7 dias uteis e enviaremos novo cartao em 5 dias uteis. "
        f"Otimo! Adorei que voces bloquearam antes de fazerem mais compras. "
        f"Exatamente, {pnome(c)}! Nosso sistema de seguranca funciona 24h para te proteger. "
        f"Muito obrigado, {a}! Continuarei cliente com certeza. "
        f"Fico feliz! A FinanceiraX preza pela sua seguranca. Algo mais? "
        f"Nao, foi perfeito. Obrigado! "
        f"Disponha! Tenha um otimo dia.",
        f"Sistema detectou fraude no cartao {contrato} com transacao suspeita de R$ {valor:,.0f}. Cartao bloqueado preventivamente, contestacao aberta protocolo {p} e estorno em 7 dias. Cliente satisfeito.",
        "Yes", "Positive",
        "Fraude detectada e cartao protegido",
        "fraude detectada, bloqueio preventivo, contestacao, estorno, novo cartao, seguranca 24h, SMS alerta, protecao fraude, transacao suspeita, satisfacao",
        "",
        "Cartao de Credito — Bloqueio e Contestacao"
    )


# ============================================================
# 5. EMPRESTIMOS — SIMULACAO E CONTRATACAO
# ============================================================

def emp_simulacao_recl(c, a, contrato, valor):
    taxa_prometida = round(random.uniform(1.5, 2.2), 2)
    taxa_real = round(taxa_prometida + random.uniform(0.5, 1.2), 2)
    p = prot()
    return entry(
        f"Boa tarde. Boa tarde, {pnome(c)}, aqui e {a} da FinanceiraX S.A. Em que posso ajudar? "
        f"Simulei um emprestimo de R$ {valor:,.0f} ontem e a taxa que aparece hoje esta diferente. "
        f"Entendo, {pnome(c)}. Vou verificar sua simulacao. Pode me informar o CPF? "
        f"Pode anotar: 987.654.321-00. "
        f"Localizei. A simulacao de ontem mostrou {taxa_prometida}% ao mes, mas a proposta de hoje esta com {taxa_real}% ao mes. "
        f"Por que mudou? A simulacao e valida por quantos dias? "
        f"A simulacao tem validade de 24 horas e as taxas sao atualizadas diariamente conforme o mercado. "
        f"Isso devia ser informado claramente! Fui ao banco por causa dessa taxa. "
        f"Tem razao, {pnome(c)}. A comunicacao devia ser mais clara. Infelizmente nao posso garantir a taxa anterior. "
        f"Posso falar com alguem para ver se conseguem a taxa original? "
        f"Posso registrar pedido de revisao. Um gerente retornara em ate 2 dias uteis. Protocolo {p}. "
        f"Dois dias sem garantia! Vou pesquisar outros bancos. "
        f"Entendo. O protocolo {p} fica registrado se quiser comparar e voltar. "
        f"Tudo bem. Tchau. "
        f"Obrigado pelo contato. Bom dia.",
        f"Cliente reclamou que taxa do emprestimo de R$ {valor:,.0f} mudou de {taxa_prometida}% para {taxa_real}% ao mes apos 24h. Agente registrou pedido de revisao protocolo {p}.",
        "No", "Negative",
        "Taxa emprestimo diferente da simulacao",
        "taxa juros, simulacao vencida, proposta emprestimo, revisao proposta, prazo simulacao, condicoes mercado, taxa ao mes, CET, contratacao emprestimo, transparencia",
        "taxa alterada",
        "Emprestimos — Simulacao e Contratacao"
    )


def emp_simulacao_elogio(c, a, contrato, valor):
    taxa = round(random.uniform(1.5, 2.2), 2)
    parcelas = random.choice([24, 36, 48])
    r = taxa / 100
    parcela = round(valor * (r * (1 + r) ** parcelas) / ((1 + r) ** parcelas - 1), 2)
    return entry(
        f"Bom dia! Bom dia, {pnome(c)}, aqui e {a} da FinanceiraX S.A. Em que posso ajudar? "
        f"Gostaria de simular um emprestimo de R$ {valor:,.0f} para reforma da minha casa. "
        f"Otimo, {pnome(c)}! Posso fazer a simulacao agora mesmo. Qual prazo prefere? "
        f"Ate 48 meses seria bom. "
        f"Para R$ {valor:,.0f} em {parcelas} meses, a taxa seria de {taxa}% ao mes. Parcelas de R$ {parcela:,.2f}. "
        f"Ficou dentro do meu orcamento! Podemos contratar agora? "
        f"Sim! Preciso apenas de comprovante de renda. Pode enviar por e-mail? "
        f"Vou enviar agora! "
        f"Documentacao recebida! Analise aprovada em menos de 2 horas. Contrato {contrato} gerado. "
        f"O valor de R$ {valor:,.0f} estara disponivel amanha. "
        f"Nossa, rapidissimo! Adorei. Muito obrigado, {a}! "
        f"Prazer em ajudar! A FinanceiraX agradece sua confianca. Bom dia!",
        f"Cliente aprovou emprestimo de R$ {valor:,.0f} em {parcelas} meses com taxa de {taxa}% ao mes. Parcelas de R$ {parcela:,.2f}. Contrato {contrato} gerado e valor disponivel em 1 dia util.",
        "Yes", "Positive",
        "Emprestimo aprovado com agilidade",
        "emprestimo aprovado, simulacao, taxa juros, parcelamento, contratacao agil, documentacao, analise rapida, credito aprovado, parcelas, reforma",
        "",
        "Emprestimos — Simulacao e Contratacao"
    )


# ============================================================
# 6. EMPRESTIMOS — RENEGOCIACAO E INADIMPLENCIA
# ============================================================

def emp_renegoc_recl(c, a, contrato, valor):
    parcelas_atrasadas = random.randint(2, 5)
    parcela_mensal = round(valor / 24, 0)
    p = prot()
    return entry(
        f"Boa tarde. Boa tarde, {pnome(c)}, meu nome e {a} da FinanceiraX S.A. Como posso ajudar? "
        f"Estou com {parcelas_atrasadas} parcelas atrasadas do emprestimo {contrato} e quero renegociar. A proposta que recebi nao e boa. "
        f"Entendo, {pnome(c)}. Vou consultar sua situacao. Parcelas de R$ {parcela_mensal:,.0f} mensais, correto? "
        f"Isso mesmo. E a proposta so tem 10% de desconto sobre os juros. "
        f"Esse e o desconto padrao da politica atual. Nao tenho autonomia para oferecer mais. "
        f"Meus amigos renegociaram com 40% em outros bancos. Podem chamar um supervisor? "
        f"Posso solicitar avaliacao por supervisor, mas pode levar ate 5 dias uteis para retorno. "
        f"Cinco dias! E enquanto isso acumulam mais juros? "
        f"Infelizmente os juros do atraso continuam correndo. Registro a solicitacao assim mesmo? "
        f"Registre. Protocolo? "
        f"Protocolo {p}. Retornaremos em breve. "
        f"Espero que sim com uma proposta decente. Tchau.",
        f"Cliente com {parcelas_atrasadas} parcelas atrasadas do contrato {contrato} reclamou da proposta de renegociacao com apenas 10% de desconto. Agente registrou pedido de revisao por supervisor protocolo {p}.",
        "No", "Negative",
        "Proposta renegociacao insuficiente",
        "renegociacao, inadimplencia, parcelas atrasadas, desconto juros, proposta inadequada, supervisor, juros atraso, contrato, negociacao, prazo pagamento",
        "desconto insuficiente",
        "Emprestimos — Renegociacao e Inadimplencia"
    )


def emp_renegoc_elogio(c, a, contrato, valor):
    desconto = random.randint(30, 50)
    meses_carencia = random.randint(2, 4)
    p = prot()
    return entry(
        f"Boa tarde. Boa tarde, {pnome(c)}, aqui e {a} da FinanceiraX S.A. Em que posso ajudar? "
        f"Estou com dificuldade para pagar o emprestimo {contrato} por desemprego. Quero renegociar. "
        f"Entendo a situacao, {pnome(c)}, e vamos encontrar uma solucao juntos. Vou verificar as opcoes. "
        f"Espero que consigam ajudar. Estou passando por um momento muito dificil. "
        f"Temos uma proposta especial: {desconto}% de desconto sobre os juros acumulados e {meses_carencia} meses de carencia. "
        f"Meu Deus, essa proposta e muito boa! {meses_carencia} meses de carencia me ajudarao a me reorganizar. "
        f"Exatamente, {pnome(c)}! E o desconto de {desconto}% sobre os juros representa economia real significativa. "
        f"Aceito a proposta! Como formalizo? "
        f"Vou gerar o aditivo agora. Protocolo {p}. Voce recebera o contrato por e-mail para assinatura digital. "
        f"Que alivio! Obrigado, {a}. Voces me ajudaram muito. "
        f"E para isso que estamos aqui, {pnome(c)}! A FinanceiraX entende o momento de cada cliente. Boa recuperacao! "
        f"Muito obrigado de verdade! Bom dia. "
        f"Bom dia! Cuide-se.",
        f"Cliente em dificuldade financeira negociou renegociacao do emprestimo {contrato} com {desconto}% de desconto e {meses_carencia} meses de carencia. Protocolo {p}. Cliente muito satisfeito.",
        "Yes", "Positive",
        "Renegociacao aceita com carencia",
        "renegociacao, carencia, desconto juros, desemprego, aditivo contrato, assinatura digital, solucao humanizada, acordo, parcelas, alivio financeiro",
        "",
        "Emprestimos — Renegociacao e Inadimplencia"
    )


# ============================================================
# 7. CREDITO ESPECIAL — CREDITO CONSIGNADO
# ============================================================

def cred_consig_recl(c, a, contrato, valor):
    margem = max(200, round(valor * 0.03))
    margem_cobrada = round(margem * 1.18)
    p = prot()
    return entry(
        f"Bom dia. Bom dia, {pnome(c)}, meu nome e {a} da FinanceiraX S.A. Em que posso ajudar? "
        f"Contratei um credito consignado {contrato} e o desconto na folha esta vindo R$ {margem_cobrada - margem:,.0f} a mais do que contratei. "
        f"Entendo sua preocupacao, {pnome(c)}. Vou consultar o contrato {contrato} agora. "
        f"A parcela deveria ser R$ {margem:,.0f} e esta saindo R$ {margem_cobrada:,.0f}. "
        f"Consultando... Identifico que houve inclusao de seguro prestamista no contrato. "
        f"Nao contratei seguro nenhum! Foi adicionado sem minha autorizacao? "
        f"O seguro prestamista e opcional. Vou verificar o contrato assinado para confirmar. "
        f"Tenho certeza que nao autorizei. Quero cancelamento e estorno. "
        f"Vou registrar cancelamento do seguro e estorno dos valores cobrados. Protocolo {p}. Prazo: 10 dias uteis. "
        f"Dez dias! E enquanto isso continuam cobrando? "
        f"O cancelamento sera retroativo a data desta solicitacao. Nao cobrara na proxima competencia. "
        f"Espero que cumpram. Isso e abusivo! "
        f"Tem razao em reclamar, {pnome(c)}. Registro tambem reclamacao formal. Protocolo {p}. Bom dia.",
        f"Cliente relatou desconto de R$ {margem_cobrada:,.0f} ao inves de R$ {margem:,.0f} no consignado {contrato} por inclusao de seguro prestamista nao autorizado. Agente registrou cancelamento e estorno.",
        "No", "Negative",
        "Desconto consignado maior que contratado",
        "credito consignado, seguro prestamista, desconto folha, margem consignavel, valor incorreto, cancelamento seguro, estorno, contrato, autorizacao, prazo analise",
        "desconto indevido",
        "Credito Especial — Credito Consignado"
    )


def cred_consig_elogio(c, a, contrato, valor):
    taxa = round(random.uniform(1.2, 1.8), 2)
    parcelas = random.choice([48, 60, 72, 84])
    r = taxa / 100
    parcela = round(valor * (r * (1 + r) ** parcelas) / ((1 + r) ** parcelas - 1), 2)
    beneficio = round(valor / 10)
    return entry(
        f"Boa tarde. Boa tarde, {pnome(c)}, aqui e {a} da FinanceiraX S.A. Em que posso ajudar? "
        f"Quero contratar um credito consignado. Sou aposentado pelo INSS com beneficio de R$ {beneficio:,.0f}. "
        f"Perfeito, {pnome(c)}! Posso fazer a simulacao agora. Qual valor precisa? "
        f"Em torno de R$ {valor:,.0f}. "
        f"Para R$ {valor:,.0f} em {parcelas} meses, a taxa consignada e de {taxa}% ao mes. Parcela de R$ {parcela:,.2f} com desconto direto no beneficio. "
        f"Muito bom! A taxa esta otima comparada com o banco onde opero normalmente. "
        f"O consignado tem as menores taxas do mercado porque o risco e muito menor. Quer contratar? "
        f"Quero sim! Quais documentos preciso? "
        f"Apenas RG, CPF e comprovante de beneficio do INSS. Pode enviar agora pelo e-mail. "
        f"Vou enviar agora mesmo. Que facilidade! "
        f"Documentacao recebida! Analise aprovada. Contrato {contrato} disponivel para assinatura digital. O credito de R$ {valor:,.0f} estara disponivel em 1 dia util. "
        f"Incrivel! Muito obrigado, {a}. Vou indicar para meus amigos aposentados! "
        f"Fico feliz, {pnome(c)}! A FinanceiraX agradece a confianca. Bom dia!",
        f"Aposentado contratou credito consignado de R$ {valor:,.0f} em {parcelas} meses com taxa de {taxa}% ao mes. Parcelas de R$ {parcela:,.2f}. Processo aprovado rapidamente. Cliente muito satisfeito.",
        "Yes", "Positive",
        "Credito consignado INSS aprovado",
        "credito consignado, aposentado INSS, taxa consignada, desconto beneficio, aprovacao rapida, documentacao simples, menor taxa mercado, assinatura digital, satisfacao, indicacao",
        "",
        "Credito Especial — Credito Consignado"
    )


# ============================================================
# 8. CREDITO ESPECIAL — PORTABILIDADE DE CREDITO
# ============================================================

def cred_portab_recl(c, a, contrato, valor):
    taxa_origem = round(random.uniform(2.5, 4.0), 2)
    taxa_destino = round(random.uniform(1.5, 2.3), 2)
    p = prot()
    return entry(
        f"Boa tarde. Boa tarde, {pnome(c)}, aqui e {a} da FinanceiraX S.A. Como posso ajudar? "
        f"Solicitei portabilidade de credito do meu banco para a FinanceiraX ha 20 dias e nada aconteceu. "
        f"Entendo, {pnome(c)}. Deixa eu verificar o status. Pode me passar o protocolo? "
        f"Protocolo {p}. O saldo devedor e R$ {valor:,.0f} com taxa de {taxa_origem}% ao mes. "
        f"Localizei. A portabilidade esta pendente porque o banco de origem nao enviou as informacoes do contrato. "
        f"Mas eu ja assinei tudo! A obrigacao de solicitar ao banco de origem nao e de voces? "
        f"A regulacao exige que o banco de origem responda em 5 dias uteis. Eles estao em atraso. "
        f"E o que a FinanceiraX faz para cobrar deles? "
        f"Enviamos notificacoes, mas dependemos da resposta deles. Posso registrar urgencia. "
        f"Enquanto isso continuo pagando {taxa_origem}% ao mes em vez de {taxa_destino}% que voces prometeram! "
        f"Entendo a frustracao, {pnome(c)}. Cada dia de atraso tem custo para voce. Vou escalar o caso. "
        f"Isso e inaceitavel! Posso reclamar no Banco Central? "
        f"Pode sim, via Bacen Jud. Escalando agora podemos resolver mais rapido. "
        f"Escale e me retorne em 24 horas. Tchau. "
        f"Registrado. Retornaremos. Ate logo.",
        f"Cliente aguarda portabilidade de R$ {valor:,.0f} ha 20 dias. Banco de origem nao respondeu. Agente escalou caso urgente com retorno em 24 horas.",
        "No", "Negative",
        "Portabilidade credito pendente 20 dias",
        "portabilidade credito, banco de origem, taxa juros, atraso portabilidade, Banco Central, Bacen, regulacao, saldo devedor, urgencia, notificacao",
        "portabilidade atrasada",
        "Credito Especial — Portabilidade de Credito"
    )


def cred_portab_elogio(c, a, contrato, valor):
    taxa_origem = round(random.uniform(2.8, 4.0), 2)
    taxa_nova = round(random.uniform(1.5, 2.3), 2)
    economia_pct = round((taxa_origem - taxa_nova) / taxa_origem * 100)
    economia_mensal = round(valor * (taxa_origem - taxa_nova) / 100, 2)
    return entry(
        f"Bom dia! Bom dia, {pnome(c)}, meu nome e {a} da FinanceiraX S.A. Como posso ajudar? "
        f"Quero fazer portabilidade do meu emprestimo. Estou pagando {taxa_origem}% ao mes em outro banco. "
        f"Excelente decisao, {pnome(c)}! Posso verificar o que conseguimos oferecer. Qual o saldo devedor? "
        f"R$ {valor:,.0f}, com 36 parcelas restantes. "
        f"Otimo. Para esse perfil, consigo oferecer {taxa_nova}% ao mes. Economia de {economia_pct}% na taxa! "
        f"Uau! Quanto vou economizar por mes? "
        f"Com essa reducao, a economia mensal seria de aproximadamente R$ {economia_mensal:,.2f}. "
        f"Perfeito! Quero fazer a portabilidade. "
        f"Vou iniciar o processo agora. Prazo total: 5 dias uteis. Voce recebera atualizacoes por SMS. Contrato {contrato} gerado. "
        f"Adorei! A FinanceiraX tem taxas muito melhores. Recomendarei para todos! "
        f"Muito obrigado pelo elogio, {pnome(c)}! Boa sorte e bom dia!",
        f"Cliente solicitou portabilidade de R$ {valor:,.0f} reduzindo taxa de {taxa_origem}% para {taxa_nova}% ao mes, economia de {economia_pct}%. Processo iniciado em 5 dias uteis. Cliente muito satisfeito.",
        "Yes", "Positive",
        "Portabilidade credito aprovada",
        "portabilidade credito, reducao taxa, economia mensal, saldo devedor, banco de origem, consentimento portabilidade, prazo 5 dias, SMS, taxa menor, satisfacao",
        "",
        "Credito Especial — Portabilidade de Credito"
    )


# ============================================================
# 9. CONSORCIO — CARTA DE CREDITO E CONTEMPLACAO
# ============================================================

def cons_carta_recl(c, a, contrato, valor):
    p = prot()
    return entry(
        f"Boa tarde. Boa tarde, {pnome(c)}, aqui e {a} da FinanceiraX S.A. Em que posso ajudar? "
        f"Fui contemplado no consorcio {contrato} mas minha carta de credito de R$ {valor:,.0f} esta bloqueada ha 15 dias. "
        f"Entendo, {pnome(c)}. Vou verificar o status da carta. "
        f"Ja tentei resolver pelo app e ninguem me deu retorno. "
        f"Localizei. A carta aguarda documentacao complementar: comprovante de renda dos ultimos 3 meses. "
        f"Mas ja enviei documentos na contratacao! Por que pedem de novo? "
        f"Com a contemplacao a analise de credito e atualizada. E procedimento padrao para liberacao da carta. "
        f"Deveriam ter me avisado! Fui surpreendido com o bloqueio. "
        f"Tem razao, {pnome(c)}. A comunicacao devia ser mais proativa. Registro reclamacao e envio orientacoes por e-mail. Protocolo {p}. "
        f"E quanto tempo apos eu enviar os documentos? "
        f"Apos o envio, analise em ate 5 dias uteis e liberacao em seguida. "
        f"Mais 5 dias! Ja perdi a oportunidade de comprar o imovel que queria. "
        f"Lamentamos muito, {pnome(c)}. Registrei reclamacao formal sobre comunicacao inadequada. "
        f"Otimo. Vou enviar os documentos. Mas precisam melhorar isso. "
        f"Tem razao. Encaminharemos seu feedback. Protocolo {p}. Bom dia.",
        f"Carta de credito de R$ {valor:,.0f} do consorcio {contrato} bloqueada ha 15 dias aguardando documentacao. Cliente frustrado com falta de comunicacao. Agente registrou reclamacao formal protocolo {p}.",
        "No", "Negative",
        "Carta credito consorcio bloqueada",
        "carta de credito, contemplacao, bloqueio carta, documentacao, comprovante renda, analise credito, comunicacao inadequada, consorcio, prazo liberacao, reclamacao",
        "carta bloqueada",
        "Consorcio — Carta de Credito e Contemplacao"
    )


def cons_carta_elogio(c, a, contrato, valor):
    p = prot()
    return entry(
        f"Boa tarde! Boa tarde, {pnome(c)}, meu nome e {a} da FinanceiraX S.A. Como posso ajudar? "
        f"Fui contemplado no consorcio de imoveis {contrato}! Quero entender como usar minha carta de credito de R$ {valor:,.0f}. "
        f"Parabens pela contemplacao, {pnome(c)}! Estou aqui para orientar. "
        f"Obrigado! Encontrei um imovel pelo valor exato da carta. Como procedo? "
        f"Perfeito! Apresente ao vendedor a carta como forma de pagamento. Vou gerar a carta de contemplacao agora. "
        f"Que rapidez! E a taxa de administracao do consorcio, como fica? "
        f"A taxa ja foi incorporada nas prestacoes pagas. Nao ha cobranca adicional na liberacao da carta. "
        f"Que excelente! Nao sabia disso. "
        f"Exatamente! E se precisar de ITBI ou escritura, pode usar parte da carta tambem. "
        f"Incrivel, nao sabia que podia! Isso facilita muito. "
        f"A FinanceiraX orienta em todos os passos. Carta de credito gerada, protocolo {p}, disponivel no app em instantes. "
        f"Adorei o atendimento! Obrigado, {a}! "
        f"Prazer todo meu! Parabens novamente. Qualquer duvida na hora da compra, ligue. Bom dia!",
        f"Cliente contemplado no consorcio {contrato} orientado sobre uso da carta de credito de R$ {valor:,.0f} para compra de imovel. Carta gerada protocolo {p}. Cliente muito satisfeito.",
        "Yes", "Positive",
        "Contemplacao consorcio orientacao bem-sucedida",
        "contemplacao, carta de credito, consorcio imovel, taxa administracao, ITBI, escritura, liberacao carta, uso carta, satisfacao, orientacao",
        "",
        "Consorcio — Carta de Credito e Contemplacao"
    )


# ============================================================
# 10. CONSORCIO — DUVIDAS SOBRE GRUPO E COTA
# ============================================================

def cons_grupo_recl(c, a, contrato, valor):
    reajuste = round(random.uniform(9, 17), 1)
    nova_parcela = round(valor * (1 + reajuste / 100))
    p = prot()
    return entry(
        f"Bom dia. Bom dia, {pnome(c)}, aqui e {a} da FinanceiraX S.A. Em que posso ajudar? "
        f"Tenho a cota {contrato} no consorcio de veiculos e minha parcela subiu {reajuste}% sem aviso. "
        f"Entendo, {pnome(c)}. Vou verificar o historico da sua cota. "
        f"A parcela era R$ {valor:,.0f} e agora esta R$ {nova_parcela:,.0f}. "
        f"Confirmado. O reajuste de {reajuste}% foi aplicado conforme contrato, baseado no IPCA e atualizacao do bem. "
        f"IPCA nao foi {reajuste}%! E por que nao recebi aviso? "
        f"O reajuste engloba tambem atualizacao do bem de referencia. Isso e previsto em contrato na clausula 8. "
        f"Nunca li que o bem seria reajustado de forma independente. Isso e confuso! "
        f"Concordo que a comunicacao podia ser mais clara. Vou enviar o detalhamento do calculo por e-mail. "
        f"Quero o detalhamento. E quero saber se posso reduzir a cota. "
        f"Para reduzir precisaria de analise do grupo. Posso registrar pedido de revisao. Prazo: 10 dias uteis. "
        f"Dez dias! E enquanto isso pago a parcela maior. "
        f"Infelizmente sim. Vou priorizar o pedido. Protocolo {p}. "
        f"Ta bom. Obrigado. Tchau. "
        f"Bom dia, {pnome(c)}.",
        f"Cliente da cota {contrato} reclamou do reajuste de {reajuste}% na parcela do consorcio de veiculos de R$ {valor:,.0f} para R$ {nova_parcela:,.0f} sem aviso previo. Agente explicou base contratual e registrou pedido de revisao.",
        "No", "Negative",
        "Reajuste consorcio sem comunicacao previa",
        "reajuste parcela, IPCA, bem de referencia, consorcio veiculos, cota, comunicacao inadequada, clausula contratual, revisao cota, aumento inesperado, prazo",
        "reajuste sem aviso",
        "Consorcio — Duvidas sobre Grupo e Cota"
    )


def cons_grupo_elogio(c, a, contrato, valor):
    assembleia = f"{random.randint(10, 28)}/{random.randint(1, 12)}/2025"
    posicao = random.randint(15, 80)
    total = random.randint(100, 200)
    carta = valor * 50
    lance_min = round(carta * 0.20)
    return entry(
        f"Boa tarde! Boa tarde, {pnome(c)}, aqui e {a} da FinanceiraX S.A. Em que posso ajudar? "
        f"Tenho algumas duvidas sobre meu consorcio de automovel, cota {contrato}. "
        f"Pois nao, {pnome(c)}! Pode perguntar a vontade. "
        f"Quando e a proxima assembleia do meu grupo? E qual minha posicao para sorteio? "
        f"A proxima assembleia e em {assembleia}. Voce esta na posicao {posicao} de {total} cotas. "
        f"E se eu quiser dar um lance, qual o valor minimo? "
        f"O lance livre e de no minimo 20% da carta de credito. Sua carta e de R$ {carta:,.0f}, lance minimo de R$ {lance_min:,.0f}. "
        f"Existe lance embutido tambem? "
        f"Existe! O lance embutido usa parte da sua propria carta como lance, sem desembolso adicional. Voce reduz a carta mas antecipa a contemplacao. "
        f"Que excelente explicacao! Nao sabia disso. Voce me ajudou muito, {a}. "
        f"Fico feliz, {pnome(c)}! Quanto mais informado o cliente, melhor a decisao. Algo mais? "
        f"Nao, ficou bem claro. Ate a proxima! "
        f"Ate mais! Estamos aqui. Bom dia!",
        f"Cliente esclareceu duvidas sobre assembleia, posicao no sorteio e tipos de lance do consorcio {contrato}. Agente explicou lance livre e embutido. Cliente muito satisfeito com as informacoes.",
        "Yes", "Positive",
        "Duvidas consorcio esclarecidas",
        "assembleia, sorteio, lance livre, lance embutido, carta de credito, posicao cota, consorcio automovel, antecipacao contemplacao, duvidas esclarecidas, satisfacao",
        "",
        "Consorcio — Duvidas sobre Grupo e Cota"
    )


# ============================================================
# MAIN
# ============================================================

def main():
    random.seed(42)

    generators = [
        (seg_contrat_recl,   seg_contrat_elogio,   [80000, 120000, 150000, 200000, 250000]),
        (seg_sinistro_recl,  seg_sinistro_elogio,  [3000, 5000, 8000, 12000, 20000]),
        (cartao_fatura_recl, cartao_fatura_elogio, [500, 800, 1200, 2000, 3500]),
        (cartao_bloqueio_recl, cartao_bloqueio_elogio, [200, 500, 800, 1500, 3000]),
        (emp_simulacao_recl, emp_simulacao_elogio, [10000, 15000, 25000, 40000, 80000]),
        (emp_renegoc_recl,   emp_renegoc_elogio,   [12000, 24000, 36000, 48000, 60000]),
        (cred_consig_recl,   cred_consig_elogio,   [5000, 8000, 12000, 15000, 25000]),
        (cred_portab_recl,   cred_portab_elogio,   [10000, 20000, 35000, 50000, 80000]),
        (cons_carta_recl,    cons_carta_elogio,    [100000, 150000, 200000, 300000, 400000]),
        (cons_grupo_recl,    cons_grupo_elogio,    [500, 800, 1200, 1800, 2500]),
    ]

    all_conversations = []
    clientes = CLIENTES.copy()
    atendentes = ATENDENTES.copy()

    for recl_fn, elogio_fn, valores in generators:
        random.shuffle(valores)
        for i in range(5):
            c = clientes[(i * 3 + len(all_conversations)) % len(clientes)]
            a = atendentes[i % len(atendentes)]
            contrato = f"FX-{random.randint(100000, 999999)}"
            valor = valores[i % len(valores)]
            all_conversations.append(recl_fn(c, a, contrato, valor))

        for i in range(5):
            c = clientes[(i * 3 + 1 + len(all_conversations)) % len(clientes)]
            a = atendentes[(i + 1) % len(atendentes)]
            contrato = f"FX-{random.randint(100000, 999999)}"
            valor = valores[i % len(valores)]
            all_conversations.append(elogio_fn(c, a, contrato, valor))

    random.shuffle(all_conversations)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(all_conversations, f, ensure_ascii=False, indent=2)

    print(f"Geradas {len(all_conversations)} conversas em: {OUTPUT}")

    satisfied_yes = sum(1 for conv in all_conversations if conv['satisfied'] == 'Yes')
    satisfied_no = sum(1 for conv in all_conversations if conv['satisfied'] == 'No')
    print(f"  Satisfeitos (Yes): {satisfied_yes}")
    print(f"  Insatisfeitos (No): {satisfied_no}")

    topics = {}
    for conv in all_conversations:
        t = conv['mined_topic']
        topics[t] = topics.get(t, 0) + 1
    print("\n  Por categoria:")
    for t, n in sorted(topics.items()):
        print(f"    {t}: {n}")


if __name__ == '__main__':
    main()
