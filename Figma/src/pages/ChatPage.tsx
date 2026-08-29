import { useState, useRef, useEffect } from "react";

type MessageRole = "user" | "ai";

interface ProductCard {
  id: string;
  name: string;
  price: number;
  detail: string;
  badge?: string;
}

interface Message {
  id: string;
  role: MessageRole;
  text: string;
  products?: ProductCard[];
  isValidating?: boolean;
  validationResult?: "allowed" | "blocked";
  validationReason?: string;
}

interface CartItem {
  id: string;
  name: string;
  price: number;
  qty: number;
}

const INITIAL_MESSAGES: Message[] = [
  {
    id: "1",
    role: "ai",
    text: "Hi! I can help you find products and build your order. Tell me what you're looking for — I'll suggest options, but every payment goes through our safety validator before anything is charged.",
  },
  {
    id: "2",
    role: "user",
    text: "I need a good laptop for video editing under ₹80,000.",
  },
  {
    id: "3",
    role: "ai",
    text: "Great choice of category. Here are three strong options within your budget. I've also flagged a useful add-on — up to you whether to include it.",
    products: [
      {
        id: "p1",
        name: "Dell XPS 15",
        price: 74999,
        detail: "i7-13th Gen · 16GB RAM · RTX 3050 · 512GB SSD",
        badge: "Best match",
      },
      {
        id: "p2",
        name: "ASUS ProArt Studiobook",
        price: 78500,
        detail: "Ryzen 9 · 32GB RAM · RTX 4060 · 1TB SSD",
      },
      {
        id: "p3",
        name: "Lenovo ThinkPad X1 Extreme",
        price: 69999,
        detail: "i7-12th Gen · 16GB RAM · RTX 3060 · 512GB SSD",
      },
    ],
  },
];

const SUGGESTED_ADDON: ProductCard = {
  id: "addon1",
  name: "USB-C Docking Station",
  price: 4999,
  detail: "4K display output · 100W PD · 7 ports",
  badge: "Suggested add-on",
};

const formatPrice = (p: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(p);

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [inputValue, setInputValue] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [checkoutState, setCheckoutState] = useState<"idle" | "validating" | "approved" | "blocked">("idle");
  const [addonDismissed, setAddonDismissed] = useState(false);
  const [addonAdded, setAddonAdded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addToCart = (product: ProductCard) => {
    setCart((prev) => {
      const existing = prev.find((i) => i.id === product.id);
      if (existing) return prev;
      return [...prev, { id: product.id, name: product.name, price: product.price, qty: 1 }];
    });
  };

  const removeFromCart = (id: string) => {
    setCart((prev) => prev.filter((i) => i.id !== id));
  };

  const cartTotal = cart.reduce((sum, i) => sum + i.price * i.qty, 0);

  const handleSend = () => {
    if (!inputValue.trim()) return;
    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      text: inputValue.trim(),
    };
    setInputValue("");
    setMessages((prev) => [...prev, userMsg]);

    setTimeout(() => {
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "ai",
        text: "Thanks for that. Let me refine my suggestions based on your preference. In the meantime, you can add any item from the current recommendations to your cart.",
      };
      setMessages((prev) => [...prev, aiMsg]);
    }, 900);
  };

  const handleCheckout = () => {
    if (cart.length === 0) return;
    setCheckoutState("validating");
    setTimeout(() => {
      setCheckoutState(cartTotal <= 80000 ? "approved" : "blocked");
    }, 2200);
  };

  const handleAcceptAddon = () => {
    addToCart(SUGGESTED_ADDON);
    setAddonAdded(true);
  };

  return (
    <div className="h-full flex overflow-hidden">
      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Page header */}
        <div
          className="shrink-0 px-8 pt-7 pb-5 border-b"
          style={{ borderColor: "var(--color-border)", background: "var(--color-card)" }}
        >
          <h1 className="text-xl font-semibold tracking-tight" style={{ color: "var(--color-foreground)" }}>
            AI Shopping Assistant
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--color-muted-foreground)" }}>
            AI can suggest — but cannot spend freely. Every payment requires validator approval.
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 scroll-container px-8 py-6 space-y-6">
          {messages.map((msg) => (
            <div key={msg.id} className="message-enter">
              {msg.role === "user" ? (
                <div className="flex justify-end">
                  <div
                    className="max-w-md px-4 py-3 rounded-2xl rounded-tr-sm text-sm leading-relaxed"
                    style={{
                      background: "var(--color-primary)",
                      color: "var(--color-primary-foreground)",
                    }}
                  >
                    {msg.text}
                  </div>
                </div>
              ) : (
                <div className="flex gap-3 max-w-2xl">
                  <div
                    className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5"
                    style={{ background: "var(--color-secondary)", border: "1px solid var(--color-border)" }}
                  >
                    <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
                      <path
                        d="M7 1L12 4v3c0 3-2 5-5 6C4 13 2 11 2 7V4L7 1z"
                        fill="var(--color-primary)"
                        fillOpacity="0.85"
                      />
                    </svg>
                  </div>
                  <div className="flex-1 space-y-4">
                    <div className="text-sm leading-relaxed" style={{ color: "var(--color-foreground)" }}>
                      {msg.text}
                    </div>
                    {msg.products && (
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {msg.products.map((product) => (
                          <ProductCardItem
                            key={product.id}
                            product={product}
                            inCart={cart.some((i) => i.id === product.id)}
                            onAdd={() => addToCart(product)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Suggested add-on */}
          {!addonDismissed && !addonAdded && (
            <div
              className="message-enter flex gap-3 max-w-2xl"
              style={{ marginLeft: "calc(1.75rem + 0.75rem)" }}
            >
              <div
                className="flex-1 rounded-xl p-4 border"
                style={{
                  background: "#fffbeb",
                  borderColor: "#fde68a",
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-medium mb-2" style={{ color: "#92400e" }}>
                      SUGGESTED ADD-ON
                    </p>
                    <p className="text-sm font-medium" style={{ color: "var(--color-foreground)" }}>
                      {SUGGESTED_ADDON.name}
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--color-muted-foreground)" }}>
                      {SUGGESTED_ADDON.detail}
                    </p>
                    <p className="text-sm font-semibold mt-2" style={{ color: "var(--color-foreground)" }}>
                      {formatPrice(SUGGESTED_ADDON.price)}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={handleAcceptAddon}
                    className="flex-1 py-2 rounded-lg text-xs font-medium transition-all"
                    style={{
                      background: "var(--color-primary)",
                      color: "var(--color-primary-foreground)",
                    }}
                  >
                    Add to cart
                  </button>
                  <button
                    onClick={() => setAddonDismissed(true)}
                    className="flex-1 py-2 rounded-lg text-xs font-medium transition-all border"
                    style={{
                      background: "white",
                      color: "var(--color-muted-foreground)",
                      borderColor: "var(--color-border)",
                    }}
                  >
                    Skip
                  </button>
                </div>
              </div>
            </div>
          )}

          {addonAdded && (
            <div
              className="message-enter ml-10 text-xs py-2 px-3 rounded-lg inline-block"
              style={{
                background: "var(--color-success-bg)",
                color: "var(--color-success)",
                border: "1px solid var(--color-success-border)",
              }}
            >
              USB-C Docking Station added to cart.
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div
          className="shrink-0 px-8 py-4 border-t"
          style={{ background: "var(--color-card)", borderColor: "var(--color-border)" }}
        >
          <div
            className="flex items-center gap-3 rounded-xl border px-4 py-3 transition-all focus-within:border-blue-400"
            style={{ background: "var(--color-muted)", borderColor: "var(--color-border)" }}
          >
            <input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Tell me what you need..."
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
              style={{ color: "var(--color-foreground)" }}
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim()}
              className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all disabled:opacity-30"
              style={{ background: "var(--color-primary)", color: "white" }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 2L11 13" />
                <path d="M22 2L15 22l-4-9-9-4 20-7z" />
              </svg>
            </button>
          </div>
          <p className="text-center text-xs mt-2.5" style={{ color: "var(--color-muted-foreground)" }}>
            AI suggestions only — payment requires Validator approval
          </p>
        </div>
      </div>

      {/* Cart sidebar */}
      <aside
        className="shrink-0 w-80 border-l flex flex-col"
        style={{ background: "var(--color-card)", borderColor: "var(--color-border)" }}
      >
        <div className="px-6 pt-7 pb-4 border-b" style={{ borderColor: "var(--color-border)" }}>
          <h2 className="text-sm font-semibold" style={{ color: "var(--color-foreground)" }}>
            Your Cart
          </h2>
          <p className="text-xs mt-0.5" style={{ color: "var(--color-muted-foreground)" }}>
            {cart.length === 0 ? "No items yet" : `${cart.length} item${cart.length > 1 ? "s" : ""}`}
          </p>
        </div>

        <div className="flex-1 scroll-container">
          {cart.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 px-6">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center"
                style={{ background: "var(--color-secondary)" }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-muted-foreground)" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z" />
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <path d="M16 10a4 4 0 01-8 0" />
                </svg>
              </div>
              <p className="text-xs text-center" style={{ color: "var(--color-muted-foreground)" }}>
                Add products from the chat to see them here
              </p>
            </div>
          ) : (
            <ul className="px-6 py-4 space-y-3">
              {cart.map((item) => (
                <li
                  key={item.id}
                  className="flex items-start justify-between gap-3 py-3 border-b last:border-0"
                  style={{ borderColor: "var(--color-border)" }}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate" style={{ color: "var(--color-foreground)" }}>
                      {item.name}
                    </p>
                    <p className="text-sm font-semibold mt-0.5" style={{ color: "var(--color-primary)" }}>
                      {formatPrice(item.price)}
                    </p>
                  </div>
                  <button
                    onClick={() => removeFromCart(item.id)}
                    className="shrink-0 w-6 h-6 rounded flex items-center justify-center transition-all hover:bg-red-50"
                    style={{ color: "var(--color-muted-foreground)" }}
                  >
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Cart footer */}
        <div className="shrink-0 px-6 py-5 border-t space-y-4" style={{ borderColor: "var(--color-border)" }}>
          {cart.length > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-sm" style={{ color: "var(--color-muted-foreground)" }}>Total</span>
              <span className="text-base font-semibold" style={{ color: "var(--color-foreground)" }}>
                {formatPrice(cartTotal)}
              </span>
            </div>
          )}

          {/* Validator status box */}
          {checkoutState !== "idle" && (
            <div
              className="rounded-lg px-4 py-3 text-xs space-y-1"
              style={{
                background:
                  checkoutState === "validating"
                    ? "var(--color-secondary)"
                    : checkoutState === "approved"
                    ? "var(--color-success-bg)"
                    : "var(--color-danger-bg)",
                border: `1px solid ${
                  checkoutState === "validating"
                    ? "var(--color-border)"
                    : checkoutState === "approved"
                    ? "var(--color-success-border)"
                    : "var(--color-danger-border)"
                }`,
              }}
            >
              {checkoutState === "validating" && (
                <>
                  <div className="flex items-center gap-2" style={{ color: "var(--color-muted-foreground)" }}>
                    <svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" opacity="0.2" />
                      <path d="M21 12a9 9 0 00-9-9" />
                    </svg>
                    <span className="font-medium">Validator checking...</span>
                  </div>
                  <p style={{ color: "var(--color-muted-foreground)" }}>Verifying price, stock, and spending limit</p>
                </>
              )}
              {checkoutState === "approved" && (
                <>
                  <div className="flex items-center gap-2" style={{ color: "var(--color-success)" }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span className="font-medium">Validator approved</span>
                  </div>
                  <p style={{ color: "var(--color-success)" }}>Price confirmed · Stock available · Within limit</p>
                </>
              )}
              {checkoutState === "blocked" && (
                <>
                  <div className="flex items-center gap-2" style={{ color: "var(--color-danger)" }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    <span className="font-medium">Payment blocked</span>
                  </div>
                  <p style={{ color: "var(--color-danger)" }}>Cart total exceeds your spending limit</p>
                </>
              )}
            </div>
          )}

          <button
            onClick={handleCheckout}
            disabled={cart.length === 0 || checkoutState === "validating" || checkoutState === "approved"}
            className="w-full py-3 rounded-xl text-sm font-semibold transition-all disabled:opacity-40"
            style={{
              background: checkoutState === "approved" ? "var(--color-accent)" : "var(--color-primary)",
              color: "white",
            }}
          >
            {checkoutState === "idle" && "Checkout"}
            {checkoutState === "validating" && "Validating..."}
            {checkoutState === "approved" && "Pay now"}
            {checkoutState === "blocked" && "Retry checkout"}
          </button>

          {/* Safety note */}
          <div className="flex items-start gap-2">
            <svg className="shrink-0 mt-0.5" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--color-muted-foreground)" strokeWidth="2" strokeLinecap="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <p className="text-xs leading-relaxed" style={{ color: "var(--color-muted-foreground)" }}>
              AI cannot complete payment independently. The Validator must approve every order.
            </p>
          </div>
        </div>
      </aside>
    </div>
  );
}

function ProductCardItem({
  product,
  inCart,
  onAdd,
}: {
  product: ProductCard;
  inCart: boolean;
  onAdd: () => void;
}) {
  return (
    <div
      className="product-card rounded-xl border p-4 flex flex-col gap-3"
      style={{
        background: "var(--color-card)",
        borderColor: "var(--color-border)",
      }}
    >
      {product.badge && (
        <span
          className="self-start text-xs font-medium px-2 py-0.5 rounded-full"
          style={{
            background: "var(--color-secondary)",
            color: "var(--color-primary)",
          }}
        >
          {product.badge}
        </span>
      )}
      <div>
        <p className="text-sm font-semibold" style={{ color: "var(--color-foreground)" }}>
          {product.name}
        </p>
        <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--color-muted-foreground)" }}>
          {product.detail}
        </p>
      </div>
      <div className="flex items-center justify-between mt-auto">
        <span className="text-sm font-bold" style={{ color: "var(--color-foreground)" }}>
          {new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
            product.price
          )}
        </span>
        <button
          onClick={onAdd}
          disabled={inCart}
          className="text-xs font-medium px-3 py-1.5 rounded-lg transition-all disabled:opacity-60"
          style={{
            background: inCart ? "var(--color-secondary)" : "var(--color-primary)",
            color: inCart ? "var(--color-muted-foreground)" : "white",
          }}
        >
          {inCart ? "Added" : "Add to cart"}
        </button>
      </div>
    </div>
  );
}
