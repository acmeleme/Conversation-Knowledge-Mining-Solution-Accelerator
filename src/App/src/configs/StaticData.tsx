const conversations = [
  {
    _attachments: "attachments/",
    _etag: '"1700d350-0000-0400-0000-673aeadc0000"',
    _rid: "L4pzAPJpN2I3AAAAAAAAAA==",
    _self: "dbs/L4pzAA==/colls/L4pzAPJpN2I=/docs/L4pzAPJpN2I3AAAAAAAAAA==/",
    _ts: 1731914460,
    conversationId: "c6430b2c-3bc6-4259-a695-db31af20e52c",
    createdAt: "2024-11-18T07:20:34.325091",
    id: "c6430b2c-3bc6-4259-a695-db31af20e52c",
    title: "Introducing the conversation",
    type: "conversation",
    updatedAt: "2024-11-18T07:21:00.469430",
    userId: "4b16c510-aecd-4016-9581-5467bfe2b8f3",
  },
  {
    _attachments: "attachments/",
    _etag: '"17003950-0000-0400-0000-673aeacf0000"',
    _rid: "L4pzAPJpN2I7AAAAAAAAAA==",
    _self: "dbs/L4pzAA==/colls/L4pzAPJpN2I=/docs/L4pzAPJpN2I7AAAAAAAAAA==/",
    _ts: 1731914447,
    conversationId: "128cbe0a-cc7e-4cd6-a217-cfe2547cf1e7",
    createdAt: "2024-11-18T07:20:47.577407",
    id: "128cbe0a-cc7e-4cd6-a217-cfe2547cf1e7",
    title: "Greeting exchange initiation",
    type: "conversation",
    updatedAt: "2024-11-18T07:20:47.707249",
    userId: "4b16c510-aecd-4016-9581-5467bfe2b8f3",
  },
];

export const historyListResponse = [].concat(...Array(0).fill(conversations));
export const historyReadResponse = {
  "conversation_id": "c6430b2c-3bc6-4259-a695-db31af20e52c",
  "messages": [
      {
          "content": "hi",
          "createdAt": "2024-11-27T08:00:38.706Z",
          "feedback": null,
          "id": "301cc2d1-aba6-47a9-8362-f44c63d52ce3",
          "role": "user",
          "context":'',
          "contentType":''
      },
      {
          "content": "Hello! How can I assist you today?",
          "createdAt": "2024-11-27T08:00:38.867Z",
          "feedback": null,
          "id": "a2521228-0f88-401f-9d39-d78e0a3ef2cd",
          "role": "assistant",
           "context":'',
          "contentType":''
      }
  ]
};
export const ChartsResponse = [
  {
    id: "AVG_HANDLING_TIME",
    chart_name: "Tempo Médio de Atendimento",
    chart_type: "card",
    layout: { row: 1, column: 3, height: 20 },
    chart_value: [
      {
        name: "Tempo Médio de Atendimento",
        value: 14,
        unit_of_measurement: "min",
      },
    ],
  },
  {
    id: "Satisfied",
    chart_name: "Satisfeitos",
    chart_type: "card",
    layout: { row: 1, column: 1, height: 20 },
    chart_value: [
      {
        name: "Satisfeitos",
        value: 50,
        unit_of_measurement: "%",
      },
    ],
  },
  {
    id: "TOTAL_CALLS",
    chart_name: "Total de Atendimentos",
    chart_type: "card",
    layout: { row: 1, column: 2, height: 20 },
    chart_value: [
      {
        name1: "Total de Atendimentos",
        value: 100,
        unit_of_measurement: "",
      },
    ],
  },
  {
    id: "TOPICS",
    chart_name: "Tópicos em Destaque",
    chart_type: "table",
    layout: { row: 3, column: 1, width: 50, height: 40 },
    chart_value: [
      {
        name: "Seguro — Contratação e Cancelamento",
        call_frequency: 10,
        average_sentiment: "negative",
      },
      {
        name: "Seguro — Sinistros e Indenizações",
        call_frequency: 10,
        average_sentiment: "negative",
      },
      {
        name: "Cartão de Crédito — Fatura e Pagamento",
        call_frequency: 10,
        average_sentiment: "neutral",
      },
      {
        name: "Cartão de Crédito — Bloqueio e Contestação",
        call_frequency: 10,
        average_sentiment: "negative",
      },
      {
        name: "Empréstimos — Simulação e Contratação",
        call_frequency: 10,
        average_sentiment: "positive",
      },
      {
        name: "Empréstimos — Renegociação e Inadimplência",
        call_frequency: 10,
        average_sentiment: "neutral",
      },
      {
        name: "Crédito Especial — Crédito Consignado",
        call_frequency: 10,
        average_sentiment: "positive",
      },
      {
        name: "Crédito Especial — Portabilidade de Crédito",
        call_frequency: 10,
        average_sentiment: "neutral",
      },
      {
        name: "Consórcio — Carta de Crédito e Contemplação",
        call_frequency: 10,
        average_sentiment: "neutral",
      },
      {
        name: "Consórcio — Dúvidas sobre Grupo e Cota",
        call_frequency: 10,
        average_sentiment: "positive",
      },
    ],
  },
  {
    id: "KEY_PHRASES",
    chart_name: "Frases-Chave",
    chart_type: "wordcloud",
    layout: { row: 3, column: 2, width: 50, height: 40 },
    chart_value: [
      {
        text: "fatura cartão",
        size: 20,
        average_sentiment: "negative",
      },
      {
        text: "taxa de juros",
        size: 22,
        average_sentiment: "neutral",
      },
      {
        text: "cobrança indevida",
        size: 19,
        average_sentiment: "negative",
      },
      {
        text: "crédito consignado",
        size: 16,
        average_sentiment: "positive",
      },
      {
        text: "sinistro pendente",
        size: 17,
        average_sentiment: "negative",
      },
      {
        text: "carta de crédito",
        size: 15,
        average_sentiment: "positive",
      },
      {
        text: "portabilidade",
        size: 13,
        average_sentiment: "neutral",
      },
      {
        text: "parcelas atrasadas",
        size: 18,
        average_sentiment: "negative",
      },
      {
        text: "contemplação consórcio",
        size: 14,
        average_sentiment: "positive",
      },
      {
        text: "renegociação",
        size: 16,
        average_sentiment: "neutral",
      },
      {
        text: "bloqueio cartão",
        size: 15,
        average_sentiment: "negative",
      },
      {
        text: "apólice seguro",
        size: 13,
        average_sentiment: "neutral",
      },
      {
        text: "margem consignável",
        size: 12,
        average_sentiment: "positive",
      },
      {
        text: "estorno",
        size: 17,
        average_sentiment: "negative",
      },
    ],
  },
  {
    id: "SENTIMENT",
    chart_name: "Visão Geral dos Tópicos",
    chart_type: "donutchart",
    layout: { row: 2, column: 1, width: 35, height: 38 },
    chart_value: [
      {
        name: "positive",
        value: 50,
      },
      {
        name: "neutral",
        value: 10,
      },
      {
        name: "negative",
        value: 40,
      },
    ],
  },
  {
    id: "AVG_HANDLING_TIME_BY_TOPIC",
    chart_name: "Tempo Médio de Atendimento por Tópico",
    chart_type: "bar",
    layout: { row: 2, column: 2, width: 65, height: 38 },
    chart_value: [
      {
        name: "Seguro — Contratação e Cancelamento",
        value: 12.5,
      },
      {
        name: "Seguro — Sinistros e Indenizações",
        value: 16.8,
      },
      {
        name: "Cartão de Crédito — Fatura e Pagamento",
        value: 14.2,
      },
      {
        name: "Cartão de Crédito — Bloqueio e Contestação",
        value: 11.3,
      },
      {
        name: "Empréstimos — Simulação e Contratação",
        value: 18.7,
      },
      {
        name: "Empréstimos — Renegociação e Inadimplência",
        value: 22.1,
      },
      {
        name: "Crédito Especial — Crédito Consignado",
        value: 13.4,
      },
      {
        name: "Crédito Especial — Portabilidade de Crédito",
        value: 15.9,
      },
      {
        name: "Consórcio — Carta de Crédito e Contemplação",
        value: 14.6,
      },
      {
        name: "Consórcio — Dúvidas sobre Grupo e Cota",
        value: 9.8,
      },
    ],
  },
];

export const sampleFiltersData = [
  {
    filter_name: "Topic",
    filter_values: [
      { key: "Seguro — Contratação e Cancelamento", displayValue: "Seguro — Contratação e Cancelamento" },
      { key: "Seguro — Sinistros e Indenizações", displayValue: "Seguro — Sinistros e Indenizações" },
      { key: "Cartão de Crédito — Fatura e Pagamento", displayValue: "Cartão de Crédito — Fatura e Pagamento" },
      { key: "Cartão de Crédito — Bloqueio e Contestação", displayValue: "Cartão de Crédito — Bloqueio e Contestação" },
      { key: "Empréstimos — Simulação e Contratação", displayValue: "Empréstimos — Simulação e Contratação" },
      { key: "Empréstimos — Renegociação e Inadimplência", displayValue: "Empréstimos — Renegociação e Inadimplência" },
      { key: "Crédito Especial — Crédito Consignado", displayValue: "Crédito Especial — Crédito Consignado" },
      { key: "Crédito Especial — Portabilidade de Crédito", displayValue: "Crédito Especial — Portabilidade de Crédito" },
      { key: "Consórcio — Carta de Crédito e Contemplação", displayValue: "Consórcio — Carta de Crédito e Contemplação" },
      { key: "Consórcio — Dúvidas sobre Grupo e Cota", displayValue: "Consórcio — Dúvidas sobre Grupo e Cota" },
    ],
  },
  {
    filter_name: "Sentiment",
    filter_values: [
      { key: "satisfied", displayValue: "Satisfeito" },
      { key: "dissatisfied", displayValue: "Insatisfeito" },
      { key: "neutral", displayValue: "Neutro" },
      { key: "all", displayValue: "Todos" },
    ],
  },
  {
    filter_name: "DateRange",
    filter_values: [
      { key: "7days", displayValue: "Últimos 7 dias" },
      { key: "14days", displayValue: "Últimos 14 dias" },
      { key: "90days", displayValue: "Últimos 90 dias" },
      { key: "yearToDate", displayValue: "Ano até hoje" },
    ],
  },
];
