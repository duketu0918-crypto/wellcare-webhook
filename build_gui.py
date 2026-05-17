# -*- coding: utf-8 -*-
import os

BASE = r'C:\LineOA_Control'

gui_code = r'''# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json, os, sys, requests, threading, subprocess
from datetime import datetime
import configparser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
STORES_FILE = os.path.join(DATA_DIR, "stores.json")
CAROUSEL_FILE = os.path.join(DATA_DIR, "carousel.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")
LINE_API_BASE = "https://api.line.me/v2/bot"

COLORS = {
    "primary": "#06C755",
    "primary_dark": "#049B42",
    "secondary": "#1E1E2E",
    "background": "#F0F2F5",
    "card_bg": "#FFFFFF",
    "text_dark": "#1A1A2E",
    "text_light": "#6B7280",
    "accent": "#FF6B6B",
    "warning": "#F59E0B",
    "success": "#10B981",
    "error": "#EF4444",
    "border": "#E5E7EB",
    "header_bg": "#1A1A2E",
    "sidebar_bg": "#16213E",
}

class DataManager:
    def __init__(self):
        self.stores = []
        self.carousel = []
        self.load_all()

    def load_all(self):
        self.load_stores()
        self.load_carousel()

    def load_stores(self):
        try:
            with open(STORES_FILE, "r", encoding="utf-8") as f:
                self.stores = json.load(f).get("stores", [])
        except Exception as e:
            self.stores = []

    def load_carousel(self):
        try:
            with open(CAROUSEL_FILE, "r", encoding="utf-8") as f:
                self.carousel = json.load(f).get("carousel_cards", [])
        except Exception:
            self.carousel = []

    def save_stores(self):
        with open(STORES_FILE, "w", encoding="utf-8") as f:
            json.dump({"stores": self.stores}, f, ensure_ascii=False, indent=2)

    def save_carousel(self):
        with open(CAROUSEL_FILE, "w", encoding="utf-8") as f:
            json.dump({"carousel_cards": self.carousel}, f, ensure_ascii=False, indent=2)

    def get_store(self, code):
        return next((s for s in self.stores if s["store_code"] == code), None)

    def get_active_stores(self):
        return [s for s in self.stores
                if s.get("status", "").lower() == "active"
                and s.get("channel_access_token", "").strip()]


class LineAPIManager:
    def __init__(self, token):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def get_rich_menus(self):
        r = requests.get(f"{LINE_API_BASE}/richmenu/list", headers=self.headers, timeout=15)
        return r.json() if r.ok else {"error": r.text}

    def create_rich_menu(self, menu_data):
        r = requests.post(f"{LINE_API_BASE}/richmenu", headers=self.headers, json=menu_data, timeout=15)
        return r.json()

    def delete_rich_menu(self, rmid):
        r = requests.delete(f"{LINE_API_BASE}/richmenu/{rmid}", headers=self.headers, timeout=15)
        return r.status_code == 200

    def upload_rich_menu_image(self, rmid, image_path):
        url = f"https://api-data.line.me/v2/bot/richmenu/{rmid}/content"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "image/png"}
        with open(image_path, "rb") as f:
            r = requests.post(url, headers=headers, data=f, timeout=30)
        return r.status_code == 200

    def set_default_rich_menu(self, rmid):
        r = requests.post(f"{LINE_API_BASE}/user/all/richmenu/{rmid}", headers=self.headers, timeout=15)
        return r.status_code == 200

    def unset_default_rich_menu(self):
        r = requests.delete(f"{LINE_API_BASE}/user/all/richmenu", headers=self.headers, timeout=15)
        return r.status_code == 200

    def build_rich_menu_object(self, store, actions):
        cfg = configparser.ConfigParser()
        cfg.read(CONFIG_FILE, encoding="utf-8")
        w   = int(cfg.get("RICHMENU", "width",  fallback="2500"))
        h   = int(cfg.get("RICHMENU", "height", fallback="1689"))
        bys = int(cfg.get("BLOCK_LAYOUT", "block_y_start", fallback="280"))
        bh  = int(cfg.get("BLOCK_LAYOUT", "block_height",  fallback="704"))

        layout = [
            (int(cfg.get("BLOCK_LAYOUT","block1_x",fallback="0")),    int(cfg.get("BLOCK_LAYOUT","block1_width",fallback="833")),  bys),
            (int(cfg.get("BLOCK_LAYOUT","block2_x",fallback="833")),   int(cfg.get("BLOCK_LAYOUT","block2_width",fallback="834")),  bys),
            (int(cfg.get("BLOCK_LAYOUT","block3_x",fallback="1667")),  int(cfg.get("BLOCK_LAYOUT","block3_width",fallback="833")),  bys),
            (int(cfg.get("BLOCK_LAYOUT","block4_x",fallback="0")),    int(cfg.get("BLOCK_LAYOUT","block4_width",fallback="833")),  bys+bh),
            (int(cfg.get("BLOCK_LAYOUT","block5_x",fallback="833")),   int(cfg.get("BLOCK_LAYOUT","block5_width",fallback="834")),  bys+bh),
            (int(cfg.get("BLOCK_LAYOUT","block6_x",fallback="1667")),  int(cfg.get("BLOCK_LAYOUT","block6_width",fallback="833")),  bys+bh),
        ]

        def make_action(atype, val):
            if atype == "postback": return {"type": "postback", "data": val, "displayText": "查看商品"}
            if atype == "message":  return {"type": "message", "text": val}
            return {"type": "uri", "uri": val}

        areas = []
        for i, (x, bw, y) in enumerate(layout):
            atype, aval = actions[i] if i < len(actions) else ("uri", "https://www.wellcare.com.tw")
            areas.append({"bounds": {"x": x, "y": y, "width": bw, "height": bh}, "action": make_action(atype, aval)})

        return {
            "size": {"width": w, "height": h},
            "selected": True,
            "name": f"{store['store_code']} 主選單",
            "chatBarText": "開啟選單",
            "areas": areas
        }


class CarouselBuilder:
    @staticmethod
    def build_carousel(cards):
        contents = [CarouselBuilder._build_bubble(c) for c in cards if c.get("enabled", True)]
        return {"type": "carousel", "contents": contents} if contents else None

    @staticmethod
    def _build_bubble(card):
        atype = card.get("action_type", "uri")
        aval  = card.get("action_value", "")
        albl  = card.get("action_label", "了解更多")
        if atype == "uri":
            act = {"type": "uri", "label": albl, "uri": aval}
        else:
            act = {"type": "message", "label": albl, "text": aval}
        return {
            "type": "bubble", "size": "mega",
            "hero": {
                "type": "image", "url": card.get("thumbnail_image_url", ""),
                "size": "full", "aspectRatio": "20:13", "aspectMode": "cover", "action": act
            },
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "16px",
                "contents": [
                    {"type": "text", "text": card.get("title", ""), "weight": "bold", "size": "xl", "color": "#1A1A2E", "wrap": True},
                    {"type": "text", "text": card.get("text", ""),  "size": "sm", "color": "#6B7280", "wrap": True, "margin": "md"}
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical", "paddingAll": "12px",
                "contents": [{"type": "button", "action": act, "style": "primary", "color": "#06C755", "height": "sm"}]
            }
        }


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("維康醫療用品 LINE OA 總控系統")
        self.geometry("1400x900")
        self.minsize(1200, 800)
        self.configure(bg=COLORS["background"])
        self.dm = DataManager()
        self.log_lines = []
        self.server_proc = None
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self._build_header()
        main = tk.Frame(self, bg=COLORS["background"])
        main.pack(fill="both", expand=True)
        self._build_sidebar(main)
        self.content_frame = tk.Frame(main, bg=COLORS["background"])
        self.content_frame.pack(side="left", fill="both", expand=True)
        self._build_notebook()
        self._build_statusbar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=COLORS["header_bg"], height=70)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        lf = tk.Frame(hdr, bg=COLORS["header_bg"])
        lf.pack(side="left", padx=20, pady=10)
        tk.Label(lf, text="💊", font=("Arial", 28), bg=COLORS["header_bg"], fg="white").pack(side="left")
        tf = tk.Frame(lf, bg=COLORS["header_bg"])
        tf.pack(side="left", padx=10)
        tk.Label(tf, text="維康醫療用品", font=("Microsoft JhengHei", 16, "bold"), bg=COLORS["header_bg"], fg="white").pack(anchor="w")
        tk.Label(tf, text="LINE OA 總控管理系統", font=("Microsoft JhengHei", 10), bg=COLORS["header_bg"], fg="#A0AEC0").pack(anchor="w")
        rf = tk.Frame(hdr, bg=COLORS["header_bg"])
        rf.pack(side="right", padx=20)
        self.clock_lbl = tk.Label(rf, text="", font=("Arial", 11), bg=COLORS["header_bg"], fg="#A0AEC0")
        self.clock_lbl.pack()
        self._tick()

    def _tick(self):
        self.clock_lbl.config(text=datetime.now().strftime("🕐 %Y-%m-%d %H:%M:%S"))
        self.after(1000, self._tick)

    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=COLORS["sidebar_bg"], width=200)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        tk.Label(sb, text="功能選單", font=("Microsoft JhengHei", 11, "bold"),
                 bg=COLORS["sidebar_bg"], fg="#A0AEC0", pady=15).pack(fill="x")
        items = [
            ("📊", "門市總覽",       0),
            ("🎨", "Rich Menu 管理", 1),
            ("🎠", "輪播卡片設定",   2),
            ("📡", "Webhook 設定",   3),
            ("📝", "操作日誌",       4),
        ]
        self.sb_btns = []
        for icon, label, idx in items:
            b = tk.Button(sb, text=f"  {icon}  {label}",
                          font=("Microsoft JhengHei", 10),
                          bg=COLORS["sidebar_bg"], fg="white",
                          activebackground=COLORS["primary"], activeforeground="white",
                          relief="flat", bd=0, pady=12, anchor="w",
                          command=lambda i=idx: self._switch_tab(i))
            b.pack(fill="x", padx=5, pady=2)
            self.sb_btns.append(b)
        tk.Label(sb, text="v1.0.0", font=("Arial", 9),
                 bg=COLORS["sidebar_bg"], fg="#4A5568").pack(side="bottom", pady=10)

    def _switch_tab(self, idx):
        self.notebook.select(idx)
        for i, b in enumerate(self.sb_btns):
            b.config(bg=COLORS["primary"] if i == idx else COLORS["sidebar_bg"])

    def _build_notebook(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TNotebook", background=COLORS["background"], borderwidth=0)
        s.configure("TNotebook.Tab", font=("Microsoft JhengHei", 10), padding=[15, 8])
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_overview = tk.Frame(self.notebook, bg=COLORS["background"])
        self.tab_richmenu = tk.Frame(self.notebook, bg=COLORS["background"])
        self.tab_carousel = tk.Frame(self.notebook, bg=COLORS["background"])
        self.tab_webhook  = tk.Frame(self.notebook, bg=COLORS["background"])
        self.tab_log      = tk.Frame(self.notebook, bg=COLORS["background"])
        self.notebook.add(self.tab_overview, text="📊 門市總覽")
        self.notebook.add(self.tab_richmenu, text="🎨 Rich Menu 管理")
        self.notebook.add(self.tab_carousel, text="🎠 輪播卡片設定")
        self.notebook.add(self.tab_webhook,  text="📡 Webhook 設定")
        self.notebook.add(self.tab_log,      text="📝 操作日誌")
        self._build_overview_tab()
        self._build_richmenu_tab()
        self._build_carousel_tab()
        self._build_webhook_tab()
        self._build_log_tab()

    def _build_statusbar(self):
        sb = tk.Frame(self, bg=COLORS["header_bg"], height=30)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self.status_var = tk.StringVar(value="✅ 系統就緒")
        tk.Label(sb, textvariable=self.status_var,
                 font=("Microsoft JhengHei", 9),
                 bg=COLORS["header_bg"], fg="#A0AEC0",
                 anchor="w", padx=15).pack(fill="x", pady=5)

    def set_status(self, msg):
        self.status_var.set(msg)
        self.log(msg)

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log_lines.append(line)
        try:
            self.log_text.config(state="normal")
            self.log_text.insert("end", line + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        except Exception:
            pass
        try:
            with open(os.path.join(LOGS_DIR, "app.log"), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    # ── Tab 0: 門市總覽 ──
    def _build_overview_tab(self):
        fr = self.tab_overview
        top = tk.Frame(fr, bg=COLORS["background"])
        top.pack(fill="x", padx=15, pady=10)
        tk.Label(top, text="📊 門市總覽",
                 font=("Microsoft JhengHei", 16, "bold"),
                 bg=COLORS["background"], fg=COLORS["text_dark"]).pack(side="left")
        tk.Button(top, text="🔄 重新整理",
                  command=self._refresh_overview,
                  bg=COLORS["primary"], fg="white",
                  font=("Microsoft JhengHei", 10),
                  relief="flat", padx=15, pady=5, cursor="hand2").pack(side="right")
        stats = tk.Frame(fr, bg=COLORS["background"])
        stats.pack(fill="x", padx=15, pady=5)
        active = len(self.dm.get_active_stores())
        total  = len(self.dm.stores)
        self._stat_card(stats, "🏪 總門市數",  str(total),         COLORS["primary"])
        self._stat_card(stats, "✅ 已設定 OA", str(active),        COLORS["success"])
        self._stat_card(stats, "⚠️ 待設定",   str(total - active), COLORS["warning"])
        cols = ("store_code", "store_name", "status", "rich_menu_id", "token_status")
        self.tree_overview = ttk.Treeview(fr, columns=cols, show="headings", height=20)
        hdrs   = {"store_code":"門市代碼","store_name":"門市名稱","status":"狀態","rich_menu_id":"Rich Menu ID","token_status":"Token 狀態"}
        widths = {"store_code":80,"store_name":280,"status":70,"rich_menu_id":320,"token_status":100}
        for c in cols:
            self.tree_overview.heading(c, text=hdrs[c])
            self.tree_overview.column(c, width=widths[c], anchor="center")
        ys = ttk.Scrollbar(fr, orient="vertical", command=self.tree_overview.yview)
        self.tree_overview.configure(yscrollcommand=ys.set)
        self.tree_overview.pack(fill="both", expand=True, padx=15, pady=5)
        ys.pack(side="right", fill="y")
        self._refresh_overview()

    def _stat_card(self, parent, title, value, color):
        card = tk.Frame(parent, bg=COLORS["card_bg"], relief="flat", bd=1)
        card.pack(side="left", padx=5, pady=5, ipadx=20, ipady=10)
        tk.Label(card, text=value, font=("Arial", 28, "bold"),
                 bg=COLORS["card_bg"], fg=color).pack()
        tk.Label(card, text=title, font=("Microsoft JhengHei", 10),
                 bg=COLORS["card_bg"], fg=COLORS["text_light"]).pack()

    def _refresh_overview(self):
        self.dm.load_stores()
        for row in self.tree_overview.get_children():
            self.tree_overview.delete(row)
        for s in self.dm.stores:
            tok  = "✅ 已設定" if s.get("channel_access_token", "").strip() else "❌ 未設定"
            rmid = s.get("rich_menu_id", "") or "—"
            tag  = "active" if s.get("channel_access_token", "").strip() else "inactive"
            self.tree_overview.insert("", "end",
                values=(s["store_code"], s["store_name"], s.get("status", "active"), rmid, tok),
                tags=(tag,))
        self.tree_overview.tag_configure("active",   background="#F0FFF4")
        self.tree_overview.tag_configure("inactive", background="#FFF5F5")
        self.set_status(f"✅ 已載入 {len(self.dm.stores)} 個門市資料")

    # ── Tab 1: Rich Menu 管理 ──
    def _build_richmenu_tab(self):
        fr = self.tab_richmenu
        top = tk.Frame(fr, bg=COLORS["background"])
        top.pack(fill="x", padx=15, pady=10)
        tk.Label(top, text="🎨 Rich Menu 管理",
                 font=("Microsoft JhengHei", 16, "bold"),
                 bg=COLORS["background"], fg=COLORS["text_dark"]).pack(side="left")

        sel_fr = tk.LabelFrame(fr, text="門市選擇", font=("Microsoft JhengHei", 10),
                                bg=COLORS["background"], padx=10, pady=8)
        sel_fr.pack(fill="x", padx=15, pady=5)
        tk.Label(sel_fr, text="選擇門市:", bg=COLORS["background"],
                 font=("Microsoft JhengHei", 10)).grid(row=0, column=0, sticky="w")
        self.store_var = tk.StringVar()
        self.store_combo = ttk.Combobox(sel_fr, textvariable=self.store_var,
                                         values=[s["store_code"] for s in self.dm.stores],
                                         width=15, state="readonly")
        self.store_combo.grid(row=0, column=1, padx=5)
        self.store_combo.bind("<<ComboboxSelected>>", self._on_store_select)
        self.store_info_lbl = tk.Label(sel_fr, text="", bg=COLORS["background"],
                                        font=("Microsoft JhengHei", 9), fg=COLORS["text_light"])
        self.store_info_lbl.grid(row=0, column=2, padx=15, sticky="w")

        img_fr = tk.LabelFrame(fr, text="Rich Menu 圖片", font=("Microsoft JhengHei", 10),
                                 bg=COLORS["background"], padx=10, pady=8)
        img_fr.pack(fill="x", padx=15, pady=5)
        self.img_path_var = tk.StringVar(value="assets/richmenu.png")
        tk.Entry(img_fr, textvariable=self.img_path_var, width=50, font=("Arial", 10)).grid(row=0, column=0, padx=5)
        tk.Button(img_fr, text="📁 瀏覽", command=self._browse_image,
                  bg=COLORS["secondary"], fg="white", font=("Microsoft JhengHei", 9),
                  relief="flat", padx=10, cursor="hand2").grid(row=0, column=1, padx=5)

        action_fr = tk.LabelFrame(fr, text="區塊動作設定 (6個區塊)",
                                   font=("Microsoft JhengHei", 10),
                                   bg=COLORS["background"], padx=10, pady=8)
        action_fr.pack(fill="x", padx=15, pady=5)
        self.block_vars = []
        block_defaults = [
            ("postback", "action=show_carousel"),
            ("uri",      "https://www.wellcare.com.tw"),
            ("uri",      "https://www.wellcare.com.tw"),
            ("uri",      "https://www.wellcare.com.tw"),
            ("uri",      "https://www.wellcare.com.tw"),
            ("uri",      "https://line.me/R/pay"),
        ]
        for i, (atype, aval) in enumerate(block_defaults):
            row = i // 2
            col_base = (i % 2) * 3
            tk.Label(action_fr, text=f"B{i+1} 類型:",
                     bg=COLORS["background"], font=("Microsoft JhengHei", 9)
                     ).grid(row=row, column=col_base, sticky="w", padx=5, pady=3)
            t_var = tk.StringVar(value=atype)
            ttk.Combobox(action_fr, textvariable=t_var,
                         values=["uri", "message", "postback"],
                         width=9, state="readonly").grid(row=row, column=col_base+1, padx=3)
            v_var = tk.StringVar(value=aval)
            tk.Entry(action_fr, textvariable=v_var, width=38,
                     font=("Arial", 9)).grid(row=row, column=col_base+2, padx=3)
            self.block_vars.append((t_var, v_var))

        btn_fr = tk.Frame(fr, bg=COLORS["background"])
        btn_fr.pack(fill="x", padx=15, pady=10)
        for txt, cmd, clr in [
            ("📋 查詢選單",   self._query_rich_menus,  COLORS["secondary"]),
            ("✨ 建立選單",   self._create_rich_menu,  COLORS["primary"]),
            ("🖼️ 上傳圖片",  self._upload_image,      "#7C3AED"),
            ("⭐ 設為預設",  self._set_default_menu,  COLORS["success"]),
            ("🗑️ 刪除選單",  self._delete_rich_menu,  COLORS["error"]),
            ("🚀 一鍵部署",  self._one_click_deploy,  COLORS["accent"]),
        ]:
            tk.Button(btn_fr, text=txt, command=cmd,
                      bg=clr, fg="white", font=("Microsoft JhengHei", 10),
                      relief="flat", padx=12, pady=8, cursor="hand2").pack(side="left", padx=5)

        res_fr = tk.LabelFrame(fr, text="執行結果", font=("Microsoft JhengHei", 10),
                                bg=COLORS["background"], padx=5, pady=5)
        res_fr.pack(fill="both", expand=True, padx=15, pady=5)
        self.rm_result = scrolledtext.ScrolledText(res_fr, height=8, state="disabled",
                                                    font=("Consolas", 9), bg="#1E1E2E", fg="#A0AEC0")
        self.rm_result.pack(fill="both", expand=True)

    def _on_store_select(self, event=None):
        code  = self.store_var.get()
        store = self.dm.get_store(code)
        if store:
            rmid = store.get("rich_menu_id", "") or "未設定"
            self.store_info_lbl.config(text=f"Rich Menu: {rmid}")

    def _browse_image(self):
        path = filedialog.askopenfilename(filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
        if path:
            self.img_path_var.set(path)

    def _get_api(self):
        code = self.store_var.get()
        if not code:
            messagebox.showwarning("提示", "請先選擇門市")
            return None, None
        store = self.dm.get_store(code)
        tok   = store.get("channel_access_token", "").strip() if store else ""
        if not tok:
            messagebox.showerror("錯誤", f"{code} 尚未設定 Channel Access Token")
            return None, None
        return LineAPIManager(tok), store

    def _show_result(self, text):
        self.rm_result.config(state="normal")
        self.rm_result.insert("end", f"[{datetime.now():%H:%M:%S}] {text}\n")
        self.rm_result.see("end")
        self.rm_result.config(state="disabled")

    def _query_rich_menus(self):
        api, store = self._get_api()
        if not api: return
        def task():
            res   = api.get_rich_menus()
            menus = res.get("richmenus", [])
            self._show_result(f"共 {len(menus)} 個 Rich Menu:")
            for m in menus:
                self._show_result(f"  ID:{m.get('richMenuId','')}  名稱:{m.get('name','')}")
            self.set_status(f"✅ {store['store_code']} 查詢完成")
        threading.Thread(target=task, daemon=True).start()

    def _create_rich_menu(self):
        api, store = self._get_api()
        if not api: return
        actions  = [(t.get(), v.get()) for t, v in self.block_vars]
        menu_obj = api.build_rich_menu_object(store, actions)
        def task():
            res  = api.create_rich_menu(menu_obj)
            rmid = res.get("richMenuId", "")
            if rmid:
                store["rich_menu_id"] = rmid
                self.dm.save_stores()
                self._show_result(f"✅ 建立成功: {rmid}")
                self.set_status(f"✅ {store['store_code']} Rich Menu 建立完成")
                self.store_info_lbl.config(text=f"Rich Menu: {rmid}")
            else:
                self._show_result(f"❌ 建立失敗: {res}")
        threading.Thread(target=task, daemon=True).start()

    def _upload_image(self):
        api, store = self._get_api()
        if not api: return
        img  = self.img_path_var.get()
        rmid = store.get("rich_menu_id", "")
        if not os.path.exists(img):
            messagebox.showerror("錯誤", f"圖片不存在: {img}"); return
        if not rmid:
            messagebox.showwarning("提示", "請先建立 Rich Menu"); return
        def task():
            ok  = api.upload_rich_menu_image(rmid, img)
            msg = "✅ 圖片上傳成功" if ok else "❌ 圖片上傳失敗"
            self._show_result(msg); self.set_status(msg)
        threading.Thread(target=task, daemon=True).start()

    def _set_default_menu(self):
        api, store = self._get_api()
        if not api: return
        rmid = store.get("rich_menu_id", "")
        if not rmid:
            messagebox.showwarning("提示", "請先建立 Rich Menu"); return
        def task():
            ok  = api.set_default_rich_menu(rmid)
            msg = f"✅ 已設為預設: {rmid}" if ok else "❌ 設定失敗"
            self._show_result(msg); self.set_status(msg)
        threading.Thread(target=task, daemon=True).start()

    def _delete_rich_menu(self):
        api, store = self._get_api()
        if not api: return
        rmid = store.get("rich_menu_id", "")
        if not rmid:
            messagebox.showwarning("提示", "無 Rich Menu ID"); return
        if not messagebox.askyesno("確認刪除", f"確定刪除\n{rmid}？"): return
        def task():
            ok = api.delete_rich_menu(rmid)
            if ok:
                store["rich_menu_id"] = ""
                self.dm.save_stores()
                self._show_result(f"✅ 已刪除: {rmid}")
            else:
                self._show_result(f"❌ 刪除失敗")
        threading.Thread(target=task, daemon=True).start()

    def _one_click_deploy(self):
        api, store = self._get_api()
        if not api: return
        img      = self.img_path_var.get()
        has_img  = os.path.exists(img)
        actions  = [(t.get(), v.get()) for t, v in self.block_vars]
        menu_obj = api.build_rich_menu_object(store, actions)
        def task():
            self._show_result("🚀 開始一鍵部署...")
            res  = api.create_rich_menu(menu_obj)
            rmid = res.get("richMenuId", "")
            if not rmid:
                self._show_result(f"❌ 建立失敗: {res}"); return
            self._show_result(f"  ✅ 建立: {rmid}")
            store["rich_menu_id"] = rmid
            self.dm.save_stores()
            if has_img:
                ok = api.upload_rich_menu_image(rmid, img)
                self._show_result(f"  {'✅' if ok else '❌'} 圖片上傳")
            ok = api.set_default_rich_menu(rmid)
            self._show_result(f"  {'✅' if ok else '❌'} 設為預設")
            self._show_result("🎉 部署完成！")
            self.set_status(f"✅ {store['store_code']} 一鍵部署完成")
        threading.Thread(target=task, daemon=True).start()

    # ── Tab 2: 輪播卡片設定 ──
    def _build_carousel_tab(self):
        fr = self.tab_carousel
        top = tk.Frame(fr, bg=COLORS["background"])
        top.pack(fill="x", padx=15, pady=10)
        tk.Label(top, text="🎠 輪播卡片設定",
                 font=("Microsoft JhengHei", 16, "bold"),
                 bg=COLORS["background"], fg=COLORS["text_dark"]).pack(side="left")
        btn_row = tk.Frame(top, bg=COLORS["background"])
        btn_row.pack(side="right")
        tk.Button(btn_row, text="💾 儲存設定", command=self._save_carousel,
                  bg=COLORS["primary"], fg="white", font=("Microsoft JhengHei", 10),
                  relief="flat", padx=12, pady=5, cursor="hand2").pack(side="left", padx=3)
        tk.Button(btn_row, text="👁️ 預覽 JSON", command=self._preview_carousel_json,
                  bg=COLORS["secondary"], fg="white", font=("Microsoft JhengHei", 10),
                  relief="flat", padx=12, pady=5, cursor="hand2").pack(side="left", padx=3)

        canvas = tk.Canvas(fr, bg=COLORS["background"], highlightthickness=0)
        ys = ttk.Scrollbar(fr, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=15)
        inner = tk.Frame(canvas, bg=COLORS["background"])
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self.card_widgets = []
        for i, card in enumerate(self.dm.carousel):
            self._build_card_editor(inner, i, card)

    def _build_card_editor(self, parent, idx, card):
        cf = tk.LabelFrame(parent, text=f"卡片 {idx+1}: {card.get('title', '')}",
                            font=("Microsoft JhengHei", 10, "bold"),
                            bg=COLORS["background"], padx=10, pady=8)
        cf.pack(fill="x", padx=5, pady=5)
        fields = [
            ("標題",     "title",               50),
            ("說明",     "text",                50),
            ("圖片 URL", "thumbnail_image_url", 70),
            ("按鈕文字", "action_label",        30),
            ("動作值",   "action_value",        70),
        ]
        vars_dict = {}
        for row, (lbl, key, w) in enumerate(fields):
            tk.Label(cf, text=lbl + ":", bg=COLORS["background"],
                     font=("Microsoft JhengHei", 9), width=10, anchor="e"
                     ).grid(row=row, column=0, sticky="e", pady=2)
            var = tk.StringVar(value=str(card.get(key, "")))
            tk.Entry(cf, textvariable=var, width=w, font=("Arial", 9)
                     ).grid(row=row, column=1, sticky="w", padx=5)
            vars_dict[key] = var
        tk.Label(cf, text="動作類型:", bg=COLORS["background"],
                 font=("Microsoft JhengHei", 9), width=10, anchor="e"
                 ).grid(row=len(fields), column=0, sticky="e", pady=2)
        at_var = tk.StringVar(value=card.get("action_type", "uri"))
        ttk.Combobox(cf, textvariable=at_var, values=["uri", "message"],
                     width=12, state="readonly").grid(row=len(fields), column=1, sticky="w", padx=5)
        vars_dict["action_type"] = at_var
        en_var = tk.BooleanVar(value=card.get("enabled", True))
        tk.Checkbutton(cf, text="啟用此卡片", variable=en_var,
                       bg=COLORS["background"], font=("Microsoft JhengHei", 9)
                       ).grid(row=len(fields)+1, column=1, sticky="w", pady=3)
        vars_dict["enabled"] = en_var
        self.card_widgets.append((idx, vars_dict))

    def _save_carousel(self):
        for idx, vd in self.card_widgets:
            if idx < len(self.dm.carousel):
                c = self.dm.carousel[idx]
                c["title"]               = vd["title"].get()
                c["text"]                = vd["text"].get()
                c["thumbnail_image_url"] = vd["thumbnail_image_url"].get()
                c["action_label"]        = vd["action_label"].get()
                c["action_value"]        = vd["action_value"].get()
                c["action_type"]         = vd["action_type"].get()
                c["enabled"]             = vd["enabled"].get()
        self.dm.save_carousel()
        messagebox.showinfo("完成", "✅ 輪播卡片設定已儲存")
        self.set_status("✅ 輪播卡片設定已儲存")

    def _preview_carousel_json(self):
        cards = []
        for idx, vd in self.card_widgets:
            if idx < len(self.dm.carousel):
                cards.append({
                    "title":               vd["title"].get(),
                    "text":                vd["text"].get(),
                    "thumbnail_image_url": vd["thumbnail_image_url"].get(),
                    "action_label":        vd["action_label"].get(),
                    "action_value":        vd["action_value"].get(),
                    "action_type":         vd["action_type"].get(),
                    "enabled":             vd["enabled"].get(),
                })
        flex = CarouselBuilder.build_carousel(cards)
        win  = tk.Toplevel(self)
        win.title("輪播 JSON 預覽")
        win.geometry("700x500")
        st = scrolledtext.ScrolledText(win, font=("Consolas", 9))
        st.pack(fill="both", expand=True, padx=10, pady=10)
        st.insert("end", json.dumps(flex, ensure_ascii=False, indent=2))
        st.config(state="disabled")

    # ── Tab 3: Webhook 設定 ──
    def _build_webhook_tab(self):
        fr = self.tab_webhook
        tk.Label(fr, text="📡 Webhook 設定",
                 font=("Microsoft JhengHei", 16, "bold"),
                 bg=COLORS["background"], fg=COLORS["text_dark"],
                 pady=10).pack(anchor="w", padx=15)

        ng_fr = tk.LabelFrame(fr, text="ngrok 設定", font=("Microsoft JhengHei", 10),
                               bg=COLORS["background"], padx=10, pady=8)
        ng_fr.pack(fill="x", padx=15, pady=5)
        tk.Label(ng_fr, text="伺服器 Port:", bg=COLORS["background"],
                 font=("Microsoft JhengHei", 10)).grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar(value="5000")
        tk.Entry(ng_fr, textvariable=self.port_var, width=10,
                 font=("Arial", 10)).grid(row=0, column=1, sticky="w", padx=5)

        url_fr = tk.LabelFrame(fr, text="各門市 Webhook URL",
                                font=("Microsoft JhengHei", 10),
                                bg=COLORS["background"], padx=10, pady=8)
        url_fr.pack(fill="x", padx=15, pady=5)
        self.webhook_domain_var = tk.StringVar(value="https://your-domain.ngrok.io")
        tk.Label(url_fr, text="Webhook Domain:", bg=COLORS["background"],
                 font=("Microsoft JhengHei", 10)).grid(row=0, column=0, sticky="w")
        tk.Entry(url_fr, textvariable=self.webhook_domain_var, width=50,
                 font=("Arial", 10)).grid(row=0, column=1, padx=5)
        tk.Button(url_fr, text="產生 URL 列表", command=self._gen_webhook_urls,
                  bg=COLORS["primary"], fg="white", font=("Microsoft JhengHei", 10),
                  relief="flat", padx=10, cursor="hand2").grid(row=0, column=2, padx=5)

        self.webhook_text = scrolledtext.ScrolledText(fr, height=12, font=("Consolas", 9),
                                                       bg="#1E1E2E", fg="#A0AEC0")
        self.webhook_text.pack(fill="both", expand=True, padx=15, pady=5)

        srv_fr = tk.Frame(fr, bg=COLORS["background"])
        srv_fr.pack(fill="x", padx=15, pady=5)
        tk.Button(srv_fr, text="▶️ 啟動 Webhook 伺服器",
                  command=self._start_webhook_server,
                  bg=COLORS["success"], fg="white",
                  font=("Microsoft JhengHei", 11, "bold"),
                  relief="flat", padx=20, pady=8, cursor="hand2").pack(side="left", padx=5)
        tk.Button(srv_fr, text="⏹️ 停止伺服器",
                  command=self._stop_webhook_server,
                  bg=COLORS["error"], fg="white",
                  font=("Microsoft JhengHei", 11, "bold"),
                  relief="flat", padx=20, pady=8, cursor="hand2").pack(side="left", padx=5)
        self.server_status_lbl = tk.Label(srv_fr, text="⏸️ 伺服器未啟動",
                                           font=("Microsoft JhengHei", 10),
                                           bg=COLORS["background"], fg=COLORS["warning"])
        self.server_status_lbl.pack(side="left", padx=15)

    def _gen_webhook_urls(self):
        domain = self.webhook_domain_var.get().rstrip("/")
        self.webhook_text.config(state="normal")
        self.webhook_text.delete("1.0", "end")
        for s in self.dm.stores:
            url = f"{domain}/webhook/{s['store_code']}"
            self.webhook_text.insert("end", f"{s['store_code']:6s} | {s['store_name']:30s} | {url}\n")
        self.webhook_text.config(state="disabled")

    def _start_webhook_server(self):
        if self.server_proc and self.server_proc.poll() is None:
            messagebox.showinfo("提示", "伺服器已在運行中"); return
        script = os.path.join(BASE_DIR, "webhook_server.py")
        if not os.path.exists(script):
            messagebox.showerror("錯誤", "找不到 webhook_server.py"); return
        self.server_proc = subprocess.Popen(
            [sys.executable, script],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        self.server_status_lbl.config(text="✅ 伺服器運行中", fg=COLORS["success"])
        self.set_status("✅ Webhook 伺服器已啟動")

    def _stop_webhook_server(self):
        if self.server_proc:
            self.server_proc.terminate()
            self.server_proc = None
        self.server_status_lbl.config(text="⏸️ 伺服器已停止", fg=COLORS["warning"])
        self.set_status("⏸️ Webhook 伺服器已停止")

    # ── Tab 4: 操作日誌 ──
    def _build_log_tab(self):
        fr = self.tab_log
        top = tk.Frame(fr, bg=COLORS["background"])
        top.pack(fill="x", padx=15, pady=10)
        tk.Label(top, text="📝 操作日誌",
                 font=("Microsoft JhengHei", 16, "bold"),
                 bg=COLORS["background"], fg=COLORS["text_dark"]).pack(side="left")
        tk.Button(top, text="🗑️ 清除日誌", command=self._clear_log,
                  bg=COLORS["error"], fg="white", font=("Microsoft JhengHei", 10),
                  relief="flat", padx=12, pady=5, cursor="hand2").pack(side="right")
        tk.Button(top, text="💾 匯出日誌", command=self._export_log,
                  bg=COLORS["secondary"], fg="white", font=("Microsoft JhengHei", 10),
                  relief="flat", padx=12, pady=5, cursor="hand2").pack(side="right", padx=5)
        self.log_text = scrolledtext.ScrolledText(fr, state="disabled",
                                                   font=("Consolas", 9),
                                                   bg="#1E1E2E", fg="#A0AEC0")
        self.log_text.pack(fill="both", expand=True, padx=15, pady=5)

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self.log_lines.clear()

    def _export_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile=f"log_{datetime.now():%Y%m%d_%H%M%S}.txt"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.log_lines))
            messagebox.showinfo("完成", f"日誌已匯出至:\n{path}")

    def _on_close(self):
        if self.server_proc and self.server_proc.poll() is None:
            if messagebox.askyesno("確認關閉", "Webhook 伺服器仍在運行，確定關閉？"):
                self.server_proc.terminate()
                self.destroy()
        else:
            self.destroy()


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
'''

out = os.path.join(BASE, 'main_gui.py')
with open(out, 'w', encoding='utf-8') as f:
    f.write(gui_code)
print(f'完成！main_gui.py 大小: {os.path.getsize(out):,} bytes')
