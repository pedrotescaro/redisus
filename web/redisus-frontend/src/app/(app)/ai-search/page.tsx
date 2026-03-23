"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { onAuthStateChanged, type User } from "firebase/auth";
import { auth } from "@/lib/firebase";
import {
  sendChatMessage,
  analyzeImageWithAI,
  getConversations,
  getConversationMessages,
  deleteConversation,
  type ChatMessage,
  type Conversation,
} from "@/services/firebase/ai-chat-service";

/* ─── Sugestões rápidas ────────────────────────────────────── */
const quickSuggestions = [
  { id: "1", text: "Buscar histórico de Maria Silva", icon: "history" },
  { id: "2", text: "Gerar relatório de evolução semanal", icon: "description" },
  { id: "3", text: "Como registrar uma nova ferida?", icon: "help" },
  { id: "4", text: "Pacientes com cicatrização atrasada", icon: "warning" },
  { id: "5", text: "Classificar tecido de granulação", icon: "biotech" },
  { id: "6", text: "Qual a conduta para úlcera venosa?", icon: "medical_services" },
];

/* ─── Componente de mensagem ──────────────────────────────── */
function MessageBubble({
  message,
  isTyping,
}: {
  message: ChatMessage;
  isTyping?: boolean;
}) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"} animate-in fade-in slide-in-from-bottom-2 duration-300`}
    >
      {/* Avatar */}
      <div
        className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
          isUser
            ? "bg-primary text-on-primary"
            : "bg-gradient-to-br from-primary/20 to-tertiary/20 text-primary"
        }`}
      >
        <span className="material-symbols-outlined text-lg">
          {isUser ? "person" : "auto_awesome"}
        </span>
      </div>

      {/* Bubble */}
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-primary text-on-primary rounded-tr-md"
            : "bg-surface-container-low text-on-surface rounded-tl-md border border-outline-variant/10"
        }`}
      >
        {isTyping ? (
          <div className="flex items-center gap-1.5 py-1">
            <span className="w-2 h-2 bg-primary/60 rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-2 h-2 bg-primary/60 rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-2 h-2 bg-primary/60 rounded-full animate-bounce [animation-delay:300ms]" />
          </div>
        ) : (
          <div className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.content}
          </div>
        )}

        {message.imageUrl && (
          <img
            src={message.imageUrl}
            alt="Imagem anexada"
            className="mt-2 max-w-full rounded-xl max-h-48 object-cover"
          />
        )}
      </div>
    </div>
  );
}

/* ─── Sidebar de conversas ────────────────────────────────── */
function ConversationSidebar({
  conversations,
  activeConversationId,
  onSelect,
  onDelete,
  onNewChat,
}: {
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNewChat: () => void;
}) {
  return (
    <div className="w-72 h-full border-r border-outline-variant/10 bg-surface-container-lowest flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-outline-variant/10">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-on-primary rounded-xl text-sm font-semibold hover:opacity-90 transition-opacity"
        >
          <span className="material-symbols-outlined text-lg">add</span>
          Nova conversa
        </button>
      </div>

      {/* History */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {conversations.length === 0 && (
          <p className="text-xs text-on-surface-variant text-center py-8">
            Nenhuma conversa ainda
          </p>
        )}
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={`group flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-colors ${
              activeConversationId === conv.id
                ? "bg-primary/10 text-primary"
                : "text-on-surface-variant hover:bg-surface-container-low"
            }`}
            onClick={() => onSelect(conv.id)}
          >
            <span className="material-symbols-outlined text-lg flex-shrink-0">
              chat_bubble_outline
            </span>
            <span className="text-sm truncate flex-grow">
              {conv.lastMessage || "Nova conversa"}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
              className="opacity-0 group-hover:opacity-100 transition-opacity text-error hover:text-error/80"
            >
              <span className="material-symbols-outlined text-base">
                delete
              </span>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Página principal ────────────────────────────────────── */
export default function AISearchPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [inputMessage, setInputMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [showSidebar, setShowSidebar] = useState(false);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  /* Auth listener */
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, setUser);
    return () => unsubscribe();
  }, []);

  /* Carrega conversas */
  useEffect(() => {
    if (user) {
      getConversations()
        .then(setConversations)
        .catch(console.error);
    }
  }, [user]);

  /* Scroll automático */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const userName =
    user?.displayName?.split(" ")[0] ||
    user?.email?.split("@")[0] ||
    "Profissional";

  /* ─── Handlers ─────────────────────────────────────────── */
  const handleSend = useCallback(
    async (text?: string) => {
      const message = text || inputMessage.trim();
      if (!message && !imageFile) return;

      setIsLoading(true);
      setInputMessage("");

      // Adiciona mensagem do usuário
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: message || "📷 Imagem enviada para análise",
        timestamp: new Date().toISOString(),
        imageUrl: imagePreview || undefined,
      };
      setMessages((prev) => [...prev, userMsg]);

      // Limpa preview de imagem
      setImagePreview(null);
      const currentImageFile = imageFile;
      setImageFile(null);

      try {
        let aiResponse: string;

        if (currentImageFile) {
          // Análise de imagem com Gemini Vision
          aiResponse = await analyzeImageWithAI(
            currentImageFile,
            message || undefined,
          );
        } else {
          // Chat de texto com Gemini
          const result = await sendChatMessage(
            message,
            activeConversationId || undefined,
          );
          aiResponse = result.response;
          setActiveConversationId(result.conversationId);
        }

        // Adiciona resposta do assistente
        const assistantMsg: ChatMessage = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: aiResponse,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);

        // Atualiza lista de conversas
        getConversations()
          .then(setConversations)
          .catch(console.error);
      } catch (error) {
        console.error("[AI Chat] Erro:", error);
        const errorMsg: ChatMessage = {
          id: `error-${Date.now()}`,
          role: "assistant",
          content:
            "Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente.\n\n" +
            `Detalhes: ${error instanceof Error ? error.message : "Erro desconhecido"}`,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
        inputRef.current?.focus();
      }
    },
    [inputMessage, imageFile, imagePreview, activeConversationId],
  );

  const handleSelectConversation = async (convId: string) => {
    setActiveConversationId(convId);
    try {
      const msgs = await getConversationMessages(convId);
      setMessages(msgs);
    } catch (error) {
      console.error("[AI Chat] Erro ao carregar conversa:", error);
    }
    setShowSidebar(false);
  };

  const handleDeleteConversation = async (convId: string) => {
    try {
      await deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        setActiveConversationId(null);
        setMessages([]);
      }
    } catch (error) {
      console.error("[AI Chat] Erro ao deletar:", error);
    }
  };

  const handleNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setShowSidebar(false);
    inputRef.current?.focus();
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = () => setImagePreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  const isEmptyChat = messages.length === 0;

  /* ─── Render ───────────────────────────────────────────── */
  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Sidebar — conversas (desktop) */}
      <div className="hidden lg:block">
        <ConversationSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelect={handleSelectConversation}
          onDelete={handleDeleteConversation}
          onNewChat={handleNewChat}
        />
      </div>

      {/* Mobile sidebar overlay */}
      {showSidebar && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setShowSidebar(false)}
          />
          <div className="relative w-72 h-full bg-surface">
            <ConversationSidebar
              conversations={conversations}
              activeConversationId={activeConversationId}
              onSelect={handleSelectConversation}
              onDelete={handleDeleteConversation}
              onNewChat={handleNewChat}
            />
          </div>
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-outline-variant/10 bg-surface-container-lowest">
          <button
            onClick={() => setShowSidebar(!showSidebar)}
            className="lg:hidden text-on-surface-variant hover:text-on-surface transition-colors"
          >
            <span className="material-symbols-outlined">menu</span>
          </button>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-tertiary flex items-center justify-center">
              <span className="material-symbols-outlined text-white text-lg">
                auto_awesome
              </span>
            </div>
            <div>
              <h1 className="text-sm font-bold font-headline text-on-surface">
                HEAL+ AI Assistant
              </h1>
              <p className="text-xs text-on-surface-variant">
                Powered by Firebase AI Logic + Gemini
              </p>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div className="hidden sm:flex items-center gap-1.5 text-xs font-medium text-primary bg-primary/10 px-3 py-1.5 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              Online
            </div>
          </div>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto">
          {isEmptyChat ? (
            /* Empty state — Welcome */
            <div className="h-full flex items-center justify-center p-6">
              <div className="max-w-2xl text-center space-y-8">
                {/* Logo animation */}
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-primary/20 to-tertiary/20 animate-pulse">
                  <span className="material-symbols-outlined text-4xl text-primary">
                    auto_awesome
                  </span>
                </div>

                <div className="space-y-3">
                  <div className="inline-flex items-center gap-2 text-xs font-bold text-primary bg-primary/10 px-4 py-2 rounded-full">
                    <span className="material-symbols-outlined text-sm">
                      verified
                    </span>
                    FIREBASE AI LOGIC + GEMINI
                  </div>
                  <h2 className="text-3xl font-extrabold font-headline text-on-surface">
                    Como posso ajudar hoje,{" "}
                    <span className="text-primary">Dr. {userName}</span>?
                  </h2>
                  <p className="text-on-surface-variant max-w-lg mx-auto">
                    Assista de IA clínica com análise de imagens, consulta de
                    pacientes e suporte em estomaterapia.
                  </p>
                </div>

                {/* Quick suggestions grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg mx-auto">
                  {quickSuggestions.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => handleSend(s.text)}
                      disabled={isLoading}
                      className="flex items-center gap-3 px-4 py-3 bg-surface-container-lowest rounded-xl border border-outline-variant/10 hover:border-primary/20 hover:bg-surface-container-low transition-all text-left group disabled:opacity-50"
                    >
                      <span className="material-symbols-outlined text-lg text-outline group-hover:text-primary transition-colors">
                        {s.icon}
                      </span>
                      <span className="text-sm text-on-surface-variant group-hover:text-on-surface transition-colors">
                        {s.text}
                      </span>
                    </button>
                  ))}
                </div>

                <p className="text-xs text-on-surface-variant">
                  <span className="material-symbols-outlined text-xs align-middle mr-1">
                    lightbulb
                  </span>
                  Dica: Envie fotos de feridas para análise com IA ou faça
                  perguntas em linguagem natural
                </p>
              </div>
            </div>
          ) : (
            /* Chat messages */
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              {isLoading && (
                <MessageBubble
                  message={{
                    id: "typing",
                    role: "assistant",
                    content: "",
                    timestamp: "",
                  }}
                  isTyping
                />
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Image preview */}
        {imagePreview && (
          <div className="px-4 py-2 border-t border-outline-variant/10 bg-surface-container-lowest">
            <div className="flex items-center gap-3 max-w-3xl mx-auto">
              <div className="relative">
                <img
                  src={imagePreview}
                  alt="Preview"
                  className="w-16 h-16 rounded-xl object-cover border border-outline-variant/20"
                />
                <button
                  onClick={() => {
                    setImagePreview(null);
                    setImageFile(null);
                  }}
                  className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-error text-on-error rounded-full flex items-center justify-center text-xs hover:opacity-80"
                >
                  ✕
                </button>
              </div>
              <p className="text-sm text-on-surface-variant">
                📷 Imagem pronta para análise — envie uma mensagem ou clique
                enviar
              </p>
            </div>
          </div>
        )}

        {/* Input area */}
        <div className="border-t border-outline-variant/10 bg-surface-container-lowest p-4">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center gap-2 bg-surface-container-low rounded-2xl border border-outline-variant/10 focus-within:border-primary/30 focus-within:ring-2 focus-within:ring-primary/10 transition-all">
              {/* Image upload button */}
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading}
                className="ml-2 p-2 text-on-surface-variant hover:text-primary transition-colors disabled:opacity-50"
                title="Enviar imagem para análise"
              >
                <span className="material-symbols-outlined">
                  add_photo_alternate
                </span>
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageSelect}
                className="hidden"
              />

              {/* Text input */}
              <input
                ref={inputRef}
                type="text"
                className="flex-grow bg-transparent border-none focus:ring-0 focus:outline-none text-sm py-3.5 text-on-surface placeholder:text-on-surface-variant font-body"
                placeholder="Pergunte algo ou envie uma foto para análise..."
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                disabled={isLoading}
              />

              {/* Send button */}
              <button
                onClick={() => handleSend()}
                disabled={
                  isLoading || (!inputMessage.trim() && !imageFile)
                }
                className="m-1.5 w-10 h-10 rounded-xl bg-primary text-on-primary flex items-center justify-center hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <span className="w-5 h-5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                ) : (
                  <span className="material-symbols-outlined text-xl">
                    send
                  </span>
                )}
              </button>
            </div>

            <p className="text-center text-[11px] text-on-surface-variant/60 mt-2">
              HEAL+ AI — Firebase AI Logic com Gemini • Análise de imagens e
              assistente clínico
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
