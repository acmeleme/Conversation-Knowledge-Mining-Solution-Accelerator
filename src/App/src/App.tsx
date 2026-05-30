import React, { useEffect, useState, useRef } from "react";
import Chart from "./components/Chart/Chart";
import Chat from "./components/Chat/Chat";
import {
  Button,
  FluentProvider,
  Subtitle2,
  Body2,
  webLightTheme,
  Avatar,
  Tag,
  Popover,
  PopoverTrigger,
  PopoverSurface,
  Divider,
  Text,
} from "@fluentui/react-components";
import { SparkleRegular, ArrowExitRegular, PersonRegular } from "@fluentui/react-icons";
import "./App.css";
import { ChatHistoryPanel } from "./components/ChatHistoryPanel/ChatHistoryPanel";
import { UserRole } from "./components/LoginPage/LoginPage";
import { clearDemoRole, setDemoRole } from "./api/api";

import {
  getUserInfo,
  getLayoutConfig,
  historyDelete,
  historyDeleteAll,
  historyList,
  historyRead,
} from "./api/api";

import { useAppContext } from "./state/useAppContext";
import { actionConstants } from "./state/ActionConstants";
import { ChatMessage, Conversation } from "./types/AppTypes";
import { AppLogo } from "./components/Svg/Svg";
import CustomSpinner from "./components/CustomSpinner/CustomSpinner";
import CitationPanel from "./components/CitationPanel/CitationPanel";
const panels = {
  DASHBOARD: "DASHBOARD",
  CHAT: "CHAT",
  CHATHISTORY: "CHATHISTORY",
};

const defaultThreeColumnConfig: Record<string, number> = {
  [panels.DASHBOARD]: 60,
  [panels.CHAT]: 40,
  [panels.CHATHISTORY]: 20,
};
const defaultSingleColumnConfig: Record<string, number> = {
  [panels.DASHBOARD]: 100,
  [panels.CHAT]: 100,
  [panels.CHATHISTORY]: 100,
};

const defaultPanelShowStates = {
  [panels.DASHBOARD]: true,
  [panels.CHAT]: true,
  [panels.CHATHISTORY]: false,
};

const Dashboard: React.FC<{ userRole: UserRole; userName: string; userEmail: string; onLogout: () => void }> = ({ userRole, userName, userEmail, onLogout }) => {
  const { state, dispatch } = useAppContext();
  const { appConfig } = state.config;
  const [panelShowStates, setPanelShowStates] = useState<
    Record<string, boolean>
  >({ ...defaultPanelShowStates });
  const [panelWidths, setPanelWidths] = useState<Record<string, number>>({
    ...defaultThreeColumnConfig,
  });
  const [layoutWidthUpdated, setLayoutWidthUpdated] = useState<boolean>(false);
  const [showClearAllConfirmationDialog, setChowClearAllConfirmationDialog] =
    useState(false);
  const [clearing, setClearing] = React.useState(false);
  const [clearingError, setClearingError] = React.useState(false);
  const [isInitialAPItriggered, setIsInitialAPItriggered] = useState(false);
  const [showAuthMessage, setShowAuthMessage] = useState<boolean | undefined>();
  const [offset, setOffset] = useState<number>(0);
  const OFFSET_INCREMENT = 25;
  const [hasMoreRecords, setHasMoreRecords] = useState<boolean>(true);
  const [userMenuOpen, setUserMenuOpen] = useState<boolean>(false);

  useEffect(() => {
    try {
      const fetchConfig = async () => {
        const configData = await getLayoutConfig();
        console.log("configData", configData);
        dispatch({ type: actionConstants.SAVE_CONFIG, payload: configData });
      };
      fetchConfig();
    } catch (error) {
      console.error("Failed to fetch chart configuration:", error);
    }
  }, []);

  const getUserInfoList = async () => {
    const userInfoList = await getUserInfo();
    if (
      userInfoList.length === 0 &&
      window.location.hostname !== "localhost" &&
      window.location.hostname !== "127.0.0.1"
    ) {
      setShowAuthMessage(true);
    } else {
      setShowAuthMessage(false);
    }
  };

  useEffect(() => {
    getUserInfoList();
  }, []);

  const roleLabel =
    userRole === "financeiro"
      ? "💼 Financeiro & Faturamento"
      : "🎧 Operador de Callcenter";

  const updateLayoutWidths = (newState: Record<string, boolean>) => {
    const noOfWidgetsOpen = Object.values(newState).filter((val) => val).length;
    if (appConfig === null) {
      return;
    }

    if (
      noOfWidgetsOpen === 1 ||
      (noOfWidgetsOpen === 2 && !newState[panels.CHAT])
    ) {
      setPanelWidths(defaultSingleColumnConfig);
    } else if (noOfWidgetsOpen === 2 && newState[panels.CHAT]) {
      const panelsInOpenState = Object.keys(newState).filter(
        (key) => newState[key]
      );
      const twoColLayouts = Object.keys(appConfig.TWO_COLUMN) as string[];
      for (let i = 0; i < twoColLayouts.length; i++) {
        const key = twoColLayouts[i] as string;
        const panelNames = key.split("_");
        const isMatched = panelsInOpenState.every((val) =>
          panelNames.includes(val)
        );
        const TWO_COLUMN = appConfig.TWO_COLUMN as Record<
          string,
          Record<string, number>
        >;
        if (isMatched) {
          setPanelWidths({ ...TWO_COLUMN[key] });
          break;
        }
      }
    } else {
      const threeColumn = appConfig.THREE_COLUMN as Record<string, number>;
      threeColumn.DASHBOARD =
        threeColumn.DASHBOARD > 55 ? threeColumn.DASHBOARD : 55;
      setPanelWidths({ ...threeColumn });
    }
  };

  useEffect(() => {
    updateLayoutWidths(panelShowStates);
  }, [state.config.appConfig]);

  const onHandlePanelStates = (panelName: string) => {
    dispatch({  type: actionConstants.UPDATE_CITATION,payload: { activeCitation: null, showCitation: false }})
    setLayoutWidthUpdated((prevFlag) => !prevFlag);
    const newState = {
      ...panelShowStates,
      [panelName]: !panelShowStates[panelName],
    };
    const isHiddenBoth = !newState[panels.DASHBOARD] && !newState[panels.CHAT];
    if (isHiddenBoth && panelName === panels.CHAT) {
      newState[panels.DASHBOARD] = true;
    } else if (isHiddenBoth && panelName === panels.DASHBOARD) {
      newState[panels.CHAT] = true;
    }
    updateLayoutWidths(newState);
    setPanelShowStates(newState);
  };

  const getHistoryListData = async () => {
    if (!hasMoreRecords) {
      return;
    }
    dispatch({
      type: actionConstants.UPDATE_CONVERSATIONS_FETCHING_FLAG,
      payload: true,
    });
    const convs = await historyList(offset);
    if (convs !== null) {
      if (convs.length === OFFSET_INCREMENT) {
        setOffset((offset) => (offset += OFFSET_INCREMENT));
        // Stopping offset increment if there were no records
      } else if (convs.length < OFFSET_INCREMENT) {
        setHasMoreRecords(false);
      }
      dispatch({
        type: actionConstants.ADD_CONVERSATIONS_TO_LIST,
        payload: convs,
      });
    }
    dispatch({
      type: actionConstants.UPDATE_CONVERSATIONS_FETCHING_FLAG,
      payload: false,
    });
  };

  const onClearAllChatHistory = async () => {
    dispatch({
      type: actionConstants.UPDATE_APP_SPINNER_STATUS,
      payload: true,
    });
    dispatch({  type: actionConstants.UPDATE_CITATION,payload: { activeCitation: null, showCitation: false }})
    setClearing(true);
    const response = await historyDeleteAll();
    if (!response.ok) {
      setClearingError(true);
    } else {
      setChowClearAllConfirmationDialog(false);
      dispatch({ type: actionConstants.UPDATE_ON_CLEAR_ALL_CONVERSATIONS });
    }
    setClearing(false);
    dispatch({
      type: actionConstants.UPDATE_APP_SPINNER_STATUS,
      payload: false,
    });
  };

  useEffect(() => {
    setIsInitialAPItriggered(true);
  }, []);

  useEffect(() => {
    if (isInitialAPItriggered) {
      (async () => {
        getHistoryListData();
      })();
    }
  }, [isInitialAPItriggered]);

  const [ASSISTANT, TOOL, ERROR, USER] = ["assistant", "tool", "error", "user"];

  const getLastRagResponse = (messages: ChatMessage[]) => {
    const lastAssistantObj = [...messages]
      .reverse()
      .find((obj) => obj.role === ASSISTANT && typeof obj.content === "string");
    if (typeof lastAssistantObj?.content === "string") {
      return lastAssistantObj.content.trim();
    }
    return null;
  };

  const onSelectConversation = async (id: string) => {
    if (!id) {
      console.error("No conversation ID found");
      return;
    }
    dispatch({
      type: actionConstants.UPDATE_CHATHISTORY_CONVERSATION_FLAG,
      payload: true,
    });
    dispatch({
      type: actionConstants.UPDATE_SELECTED_CONV_ID,
      payload: id,
    });
    dispatch({
      type: actionConstants.SET_LAST_RAG_RESPONSE,
      payload: null,
    });
    try {
      const responseMessages = await historyRead(id);

      if (responseMessages) {
        dispatch({
          type: actionConstants.SHOW_CHATHISTORY_CONVERSATION,
          payload: {
            id,
            messages: responseMessages,
          },
        });
      }
      const lastRagResponse = getLastRagResponse(responseMessages);
      dispatch({
        type: actionConstants.SET_LAST_RAG_RESPONSE,
        payload: lastRagResponse,
      });
    } catch (error) {
      console.error("Error fetching conversation messages:", error);
    } finally {
      dispatch({
        type: actionConstants.UPDATE_CHATHISTORY_CONVERSATION_FLAG,
        payload: false,
      });
    }
  };

  const onClickClearAllOption = () => {
    setChowClearAllConfirmationDialog((prevFlag) => !prevFlag);
  };

  const onHideClearAllDialog = () => {
    setChowClearAllConfirmationDialog((prevFlag) => !prevFlag);
    setTimeout(() => {
      setClearingError(false);
    }, 1000);
  };

  return (
    <FluentProvider
      theme={webLightTheme}
      style={{ height: "100%", backgroundColor: "#F5F5F5" }}
    >
      <CustomSpinner loading={state.showAppSpinner} label="Please wait.....!" />
      <div className="header">
        <div className="header-left-section">
          <AppLogo />
          <Subtitle2>
            FinanceiraX01 Bank <Body2 style={{ gap: "10px" }}>| Seu Futuro, Nosso Compromisso</Body2>
          </Subtitle2>
          {/* Role badge */}
          <Tag
            shape="circular"
            size="small"
            style={{
              marginLeft: 12,
                backgroundColor: userRole === "financeiro" ? "#dff6dd" : "#dce9f8",
                color: userRole === "financeiro" ? "#107c10" : "#0078d4",
              fontWeight: 600,
            }}
          >
              {userRole === "financeiro" ? "💼 Financeiro" : "🎧 Operador"}
          </Tag>
        </div>
        <div className="header-right-section">
          <Button
            appearance="subtle"
            onClick={() => onHandlePanelStates(panels.DASHBOARD)}
          >
            {`${
              panelShowStates?.[panels.DASHBOARD] ? "Hide" : "Show"
            } Dashboard`}
          </Button>
          <Button
            icon={<SparkleRegular />}
            appearance="subtle"
            onClick={() => onHandlePanelStates(panels.CHAT)}
          >
            {`${panelShowStates?.[panels.CHAT] ? "Hide" : "Show"} Chat`}
          </Button>
          <Popover
            open={userMenuOpen}
            onOpenChange={(_, data) => setUserMenuOpen(data.open)}
            positioning="below-end"
          >
            <PopoverTrigger>
              <div style={{ cursor: "pointer" }}>
                <Avatar name={userName || userEmail} title={userName || userEmail} />
              </div>
            </PopoverTrigger>
            <PopoverSurface style={{ padding: 0, minWidth: 240, borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}>
              {/* Profile info */}
              <div style={{ padding: "16px", display: "flex", alignItems: "center", gap: 12 }}>
                <Avatar name={userName || userEmail} size={40} />
                <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
                  <Text weight="semibold" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {userName || userEmail || "Usuário"}
                  </Text>
                  {userEmail && (
                    <Text size={200} style={{ color: "#616161", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {userEmail}
                    </Text>
                  )}
                  <Text size={200} style={{ color: "#616161" }}>
                    {roleLabel}
                  </Text>
                </div>
              </div>
              <Divider />
              {/* Menu items */}
              <div style={{ padding: "4px 0 8px" }}>
                <button
                  onClick={() => setUserMenuOpen(false)}
                  style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "8px 16px", background: "none", border: "none", cursor: "pointer", fontSize: 14, color: "#242424" }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#f5f5f5")}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                >
                  <PersonRegular style={{ fontSize: 16 }} />
                  Ver Perfil
                </button>
                <button
                  onClick={() => { setUserMenuOpen(false); onLogout(); }}
                  style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "8px 16px", background: "none", border: "none", cursor: "pointer", fontSize: 14, color: "#c50f1f" }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#fdf3f4")}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                >
                  <ArrowExitRegular style={{ fontSize: 16 }} />
                  Trocar Perfil
                </button>
              </div>
            </PopoverSurface>
          </Popover>
        </div>
      </div>
      <div className="main-container">
        {/* LEFT PANEL: DASHBOARD */}
        {panelShowStates?.[panels.DASHBOARD] && (
          <div
            className="left-section"
            style={{ width: `${panelWidths[panels.DASHBOARD]}%` }}
          >
            <Chart layoutWidthUpdated={layoutWidthUpdated} />
          </div>
        )}
        {/* MIDDLE PANEL: CHAT */}
        {panelShowStates?.[panels.CHAT] && (
          <div
            style={{
              width: `${panelWidths[panels.CHAT]}%`,
            }}
          >
            <Chat
              onHandlePanelStates={onHandlePanelStates}
              panels={panels}
              panelShowStates={panelShowStates}
            />
          </div>
        )}
        {state.citation.showCitation && state.citation.currentConversationIdForCitation !== "" && (
          <div
            style={{
              // width: `${panelWidths[panels.DASHBOARD]}%`,
              width: `${panelWidths[panels.CHATHISTORY] || 17}%`,
              // minWidth: '30%'
            }}
          >
            <CitationPanel activeCitation={state.citation.activeCitation}  />

          </div>
        )}
        {/* RIGHT PANEL: CHAT HISTORY */}
        {panelShowStates?.[panels.CHAT] &&
          panelShowStates?.[panels.CHATHISTORY] && (
            <div
              style={{
                width: `${panelWidths[panels.CHATHISTORY]}%`,
              }}
            >
              <ChatHistoryPanel
                clearing={clearing}
                clearingError={clearingError}
                handleFetchHistory={() => getHistoryListData()}
                onClearAllChatHistory={onClearAllChatHistory}
                onClickClearAllOption={onClickClearAllOption}
                onHideClearAllDialog={onHideClearAllDialog}
                onSelectConversation={onSelectConversation}
                showClearAllConfirmationDialog={showClearAllConfirmationDialog}
              />
              {/* {useAppContext?.state.isChatHistoryOpen &&
            useAppContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured && <ChatHistoryPanel />} */}
            </div>
          )}
      </div>
    </FluentProvider>
  );
};

// App wrapper: autentica via Azure EasyAuth (Entra ID) em produção
// ou usa x-demo-role do localStorage em desenvolvimento local
const App: React.FC = () => {
  const [userInfo, setUserInfo] = useState<{ name: string; email: string; role: UserRole } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Tenta obter identidade via EasyAuth (/.auth/me)
    const authenticate = async () => {
      try {
        const r = await fetch("/.auth/me");
        if (!r.ok) {
          // /.auth/me indisponível — com requireAuthentication=true o usuário já está
          // autenticado; qualquer falha aqui é infra, não sessão expirada → não redirecionar.
          throw new Error(`/.auth/me: status ${r.status}`);
        }
        let data: any[];
        try {
          data = await r.json();
        } catch {
          throw new Error("/.auth/me: JSON inválido");
        }
        const principal = data?.[0];
        if (!principal?.user_id) {
          // Headers Easy Auth ausentes (ambiente local sem Easy Auth)
          throw new Error("/.auth/me: principal ou user_id ausente");
        }
        // Azure Easy Auth retorna snake_case: user_id, user_claims
        const claims: any[] = principal.user_claims ?? [];

        // Log para diagnosticar quais claims o Easy Auth está retornando neste tenant
        console.debug("[Auth] /.auth/me claims:", claims.map((c: any) => `${c.typ}=${c.val}`));

        // Extrai email/UPN — tenta todos os claim types conhecidos do AAD v1 e v2.
        // AAD v1.0: unique_name, upn, emailaddress (WS-Fed long URIs)
        // AAD v2.0: preferred_username, email (curtos/OIDC)
        const findClaim = (...types: string[]) =>
          types.reduce<string | undefined>(
            (found, t) => found ?? claims.find((c: any) => c.typ === t)?.val,
            undefined
          );

        const email: string = (
          findClaim(
            "preferred_username",
            "email",
            "unique_name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
            "http://schemas.microsoft.com/identity/claims/preferred_username"
          ) ??
          // Último recurso: procura qualquer claim cujo valor contenha '@' (email-like)
          claims.find((c: any) => typeof c.val === "string" && c.val.includes("@"))?.val ??
          principal.user_id ??
          ""
        ).toLowerCase().trim();

        // Extrai nome de exibição — prefere display name, mas usa email se nome for o GUID/OID
        const rawName: string =
          findClaim(
            "name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
            "http://schemas.microsoft.com/identity/claims/displayname",
            "preferred_username",
            "email",
            "unique_name"
          ) ?? principal.user_id ?? "";
        // Se o nome for idêntico ao OID (GUID), usa o email em seu lugar
        const isGuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(rawName);
        const name: string = isGuid ? (email || rawName) : rawName;

        // Mapeamento UPN → papel RBAC
        // Qualquer usuário autenticado pelo Entra ID recebe "operador" por padrão.
        // Recebe "financeiro" se o email contiver "financeiro" ou se tiver a claim de roles.
        let role: UserRole = "operador";
        if (
          email.includes("financeiro") ||
          claims.some((c: any) => c.typ === "roles" && c.val === "financeiro") ||
          email.startsWith("financeiro-faturamento@")
        ) {
          role = "financeiro";
        }

        // Sincroniza a role no localStorage para que api.ts injete o header x-demo-role
        setDemoRole(role);

        setUserInfo({ name: name || email, email, role });
        setLoading(false);
      } catch {
        const isLocal =
          window.location.hostname === "localhost" ||
          window.location.hostname === "127.0.0.1";
        if (isLocal) {
          setUserInfo({ name: "Dev Local", email: "", role: "operador" });
          setLoading(false);
        } else {
          window.location.href = `/.auth/login/aad?post_login_redirect_uri=${encodeURIComponent(window.location.href)}`;
        }
      }
    };
    authenticate();
  }, []);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", fontFamily: "Segoe UI, sans-serif", color: "#0078d4" }}>
        Autenticando...
      </div>
    );
  }

  if (!userInfo) return null;

  const handleLogout = () => {
    clearDemoRole();
    window.location.href = `/.auth/logout?post_logout_redirect_uri=${encodeURIComponent(window.location.origin)}`;
  };

  return <Dashboard userRole={userInfo.role} userName={userInfo.name} userEmail={userInfo.email} onLogout={handleLogout} />;
};

export default App;
