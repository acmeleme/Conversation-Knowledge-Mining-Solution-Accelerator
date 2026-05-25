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
    chart_name: "Average Handling Time",
    chart_type: "card",
    layout: { row: 1, column: 3, height: 20 },
    chart_value: [
      {
        name: "Average Handling Time",
        value: 17,
        unit_of_measurement: "mins",
      },
    ],
  },
  {
    id: "Satisfied",
    chart_name: "Satisfied",
    chart_type: "card",
    layout: { row: 1, column: 1, height: 20 },
    chart_value: [
      {
        name: "Satisfied",
        value: 100,
        unit_of_measurement: "%",
      },
    ],
  },
  {
    id: "TOTAL_CALLS",
    chart_name: "Total Calls",
    chart_type: "card",
    layout: { row: 1, column: 2, height: 20 },
    chart_value: [
      {
        name1: "Total Calls",
        value: 105,
        unit_of_measurement: "",
      },
    ],
  },
  {
    id: "TOPICS",
    chart_name: "Trending Topics",
    chart_type: "table",
    layout: { row: 3, column: 1, width: 50, height: 40 },
    chart_value: [
      {
        name: "Account Management",
        call_frequency: 13,
        average_sentiment: "neutral",
      },
      {
        name: "Billing Issues",
        call_frequency: 12,
        average_sentiment: "neutral",
      },
      {
        name: "Device Troubleshooting",
        call_frequency: 23,
        average_sentiment: "neutral",
      },
      {
        name: "Internet Connectivity",
        call_frequency: 18,
        average_sentiment: "neutral",
      },
      {
        name: "Lost or Stolen Devices",
        call_frequency: 9,
        average_sentiment: "negative",
      },
      {
        name: "Mobile Plan Options",
        call_frequency: 11,
        average_sentiment: "positive",
      },
      {
        name: "Parental Controls",
        call_frequency: 7,
        average_sentiment: "neutral",
      },
      {
        name: "Service Activation",
        call_frequency: 23,
        average_sentiment: "neutral",
      },
    ],
  },
  {
    id: "KEY_PHRASES",
    chart_name: "Key Phrases",
    chart_type: "wordcloud",
    layout: { row: 3, column: 2, width: 50, height: 40 },
    chart_value: [
      {
        text: "account number",
        size: 7,
        average_sentiment: "negative",
      },
      {
        text: "customer service",
        size: 16,
        average_sentiment: "neutral",
      },
      {
        text: "network coverage",
        size: 22,
        average_sentiment: "neutral",
      },
      {
        text: "call forwarding",
        size: 20,
        average_sentiment: "negative",
      },
      {
        text: "promotional offers",
        size: 10,
        average_sentiment: "neutral",
      },
      {
        text: "international roaming",
        size: 11,
        average_sentiment: "neutral",
      },
      {
        text: "feedback",
        size: 16,
        average_sentiment: "neutral",
      },
      {
        text: "technical team",
        size: 10,
        average_sentiment: "neutral",
      },
      {
        text: "troubleshooting steps",
        size: 7,
        average_sentiment: "neutral",
      },
    ],
  },
  {
    id: "SENTIMENT",
    chart_name: "Topics Overview",
    chart_type: "donutchart",
    layout: { row: 2, column: 1, width: 35, height: 38 },
    chart_value: [
      {
        name: "positive",
        value: 60,
      },
      {
        name: "neutral",
        value: 10,
      },
      {
        name: "negative",
        value: 30,
      },
    ],
  },
  {
    id: "AVG_HANDLING_TIME_BY_TOPIC",
    chart_name: "Average Handling Time By Topic",
    chart_type: "bar",
    layout: { row: 2, column: 2, width: 65, height: 38 },
    chart_value: [
      {
        name: "Account Management",
        value: 12.5,
      },
      {
        name: "Billing Issues",
        value: 18.2,
      },
      {
        name: "Device Troubleshooting",
        value: 22.7,
      },
      {
        name: "Internet Connectivity",
        value: 15.3,
      },
      {
        name: "Lost or Stolen Devices",
        value: 14.1,
      },
      {
        name: "Mobile Plan Options",
        value: 10.8,
      },
      {
        name: "Parental Controls",
        value: 9.4,
      },
      {
        name: "Service Activation",
        value: 11.6,
      },
    ],
  },
];

export const sampleFiltersData = [
  {
    filter_name: "Topic",
    filter_values: [
      { key: "Account Management", displayValue: "Account Management" },
      { key: "Billing Issues", displayValue: "Billing Issues" },
      { key: "Device Troubleshooting", displayValue: "Device Troubleshooting" },
      { key: "Internet Connectivity", displayValue: "Internet Connectivity" },
      { key: "Lost or Stolen Devices", displayValue: "Lost or Stolen Devices" },
      { key: "Mobile Plan Options", displayValue: "Mobile Plan Options" },
      { key: "Parental Controls", displayValue: "Parental Controls" },
      { key: "Service Activation", displayValue: "Service Activation" },
    ],
  },
  {
    filter_name: "Sentiment",
    filter_values: [
      { key: "satisfied", displayValue: "Satisfied" },
      { key: "dissatisfied", displayValue: "Dissatisfied" },
      { key: "neutral", displayValue: "Neutral" },
      { key: "all", displayValue: "All" },
    ],
  },
  {
    filter_name: "DateRange",
    filter_values: [
      { key: "7days", displayValue: "Last 7 days" },
      { key: "14days", displayValue: "Last 14 days" },
      { key: "90days", displayValue: "Last 90 days" },
      { key: "yearToDate", displayValue: "Year to Date" },
    ],
  },
];
