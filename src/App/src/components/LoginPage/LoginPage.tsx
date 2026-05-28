import React, { useState } from "react";
import "./LoginPage.css";

export type DemoRole = "financeiro" | "operador" | "callcenter";

interface RoleCard {
  role: DemoRole;
  user: string;
  label: string;
  description: string;
  badge: string;
  badgeColor: string;
  topics: string[];
  icon: string;
}

const ROLES: RoleCard[] = [
  {
    role: "financeiro",
    user: "financeiro-faturamento@MngEnvMCAP197214.onmicrosoft.com",
    label: "Financeiro & Faturamento",
    description: "Acesso completo a todos os tópicos do callcenter, incluindo Cartão de Crédito.",
    badge: "Acesso Total",
    badgeColor: "#107c10",
    topics: ["Seguro", "Empréstimos", "Crédito Especial", "Consórcio", "Cartão de Crédito"],
    icon: "💼",
  },
  {
    role: "operador",
    user: "operador-callcenter@MngEnvMCAP197214.onmicrosoft.com",
    label: "Operador de Callcenter",
    description: "Acesso a todos os tópicos, exceto Cartão de Crédito (Fatura, Bloqueio e Contestação).",
    badge: "Acesso Restrito",
    badgeColor: "#0078d4",
    topics: ["Seguro", "Empréstimos", "Crédito Especial", "Consórcio"],
    icon: "🎧",
  },
  {
    role: "callcenter",
    user: "visitante@demo",
    label: "Visitante / Demo",
    description: "Perfil padrão de demonstração com acesso geral ao sistema.",
    badge: "Demo",
    badgeColor: "#8a8886",
    topics: ["Seguro", "Empréstimos", "Crédito Especial", "Consórcio"],
    icon: "👤",
  },
];

interface LoginPageProps {
  onLogin: (role: DemoRole, userName: string) => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  const [selected, setSelected] = useState<DemoRole | null>(null);

  const handleLogin = () => {
    if (!selected) return;
    const card = ROLES.find((r) => r.role === selected)!;
    onLogin(selected, card.user);
  };

  return (
    <div className="login-page">
      <div className="login-container">
        {/* Header */}
        <div className="login-header">
          <div className="login-logo">
            <span className="login-logo-icon">🏦</span>
          </div>
          <h1 className="login-title">FinanceiraX S.A.</h1>
          <p className="login-subtitle">Callcenter Inteligente — Plataforma de IA</p>
          <div className="login-demo-badge">🔒 Modo Demonstração — Selecione seu perfil de acesso</div>
        </div>

        {/* Role cards */}
        <div className="login-cards">
          {ROLES.map((card) => (
            <div
              key={card.role}
              className={`login-card ${selected === card.role ? "login-card--selected" : ""}`}
              onClick={() => setSelected(card.role)}
            >
              <div className="login-card-header">
                <span className="login-card-icon">{card.icon}</span>
                <div className="login-card-title-group">
                  <span className="login-card-title">{card.label}</span>
                  <span
                    className="login-card-badge"
                    style={{ backgroundColor: card.badgeColor }}
                  >
                    {card.badge}
                  </span>
                </div>
                {selected === card.role && (
                  <span className="login-card-check">✓</span>
                )}
              </div>

              <p className="login-card-user">{card.user}</p>
              <p className="login-card-description">{card.description}</p>

              <div className="login-card-topics">
                <span className="login-card-topics-label">Tópicos disponíveis:</span>
                <div className="login-card-topic-list">
                  {card.topics.map((t) => (
                    <span key={t} className="login-card-topic-chip">{t}</span>
                  ))}
                  {card.role === "operador" && (
                    <span className="login-card-topic-chip login-card-topic-chip--blocked">
                      🚫 Cartão de Crédito
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Login button */}
        <button
          className={`login-button ${selected ? "login-button--active" : ""}`}
          onClick={handleLogin}
          disabled={!selected}
        >
          {selected ? `Entrar como ${ROLES.find((r) => r.role === selected)?.label}` : "Selecione um perfil para continuar"}
        </button>

        <p className="login-footer-note">
          ℹ️ Em produção, o acesso é controlado pelo <strong>Microsoft Entra ID (EasyAuth)</strong> — o perfil é determinado automaticamente pelo UPN autenticado.
          Este seletor é utilizado apenas para <strong>desenvolvimento local</strong> sem EasyAuth.
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
