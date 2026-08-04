# -*- coding: utf-8 -*-
"""
維康醫療用品 LINE OA 總控管理系統
main_gui.py v2.2.1
─────────────────────────────────────────────────────────
修正內容（相對於 v2.2.0）：
  1. load_carousel()  → 正確解析 {"cards":[...]} 格式
  2. save_carousel()  → 以 {"cards":[...]} 格式寫回
  3. _car_load()      → action key 對應修正 (uri/text/data)
  Rich Menu 程式碼完全未動。
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import threading
import requests
from datetime import datetime

# ── 路徑設定 ──────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
STORES_F   = os.path.join(DATA_DIR, "stores.json")
RM_CFG_F   = os.path.join(DATA_DIR, "rich_menu_config.json")
CAROUSEL_F = os.path.join(DATA_DIR, "carousel.json")

WEBHOOK_BASE = "https://wellcare-webhook.onrender.com/webhook"

# ── Rich Menu 版面規格 ─────────────────────────────────
RM_W, RM_H        = 2500, 1689
HEADER_H          = 280
BLOCK_Y           = 280
BLOCK_H           = 704
BLOCKS_LAYOUT = [
    {"x":    0, "w":  833},
    {"x":  833, "w":  834},
    {"x": 1667, "w":  833},
    {"x":    0, "w":  833},
    {"x":  833, "w":  834},
    {"x": 1667, "w":  833},
]

# ── 顏色主題 ──────────────────────────────────────────
C = {
    "sidebar_bg"  : "#1a2332",
    "sidebar_sel" : "#00b894",
    "sidebar_fg"  : "#cdd6e0",
    "header_bg"   : "#1a2332",
    "header_fg"   : "#ffffff",
    "main_bg"     : "#f0f2f5",
    "card_bg"     : "#ffffff",
    "teal"        : "#00b894",
    "blue"        : "#0984e3",
    "orange"      : "#e67e22",
    "red"         : "#e74c3c",
    "purple"      : "#6c5ce7",
    "dark"        : "#2d3436",
    "text"        : "#2d3436",
    "sub"         : "#636e72",
    "border"      : "#dfe6e9",
    "log_bg"      : "#1e2a3a",
    "log_fg"      : "#00ff88",
}

# ════════════════════════════════════════════════════════
#  資料載入 / 儲存
# ════════════════════════════════════════════════════════
def load_stores():
    """載入 stores.json，回傳 list[dict]"""
    if not os.path.exists(STORES_F):
        return []
    try:
        with open(STORES_F, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            print(f"[ERROR] stores.json 格式錯誤: 應為 list，實際為 {type(raw)}")
            return []
        result = []
        for item in raw:
            if isinstance(item, dict):
                result.append(item)
            else:
                print(f"[WARN] 跳過非 dict 項目: {item}")
        print(f"[OK] 載入 {len(result)} 筆門市資料")
        return result
    except Exception as e:
        print(f"[ERROR] 載入 stores.json 失敗: {e}")
        return []

def load_rm_config():
    if not os.path.exists(RM_CFG_F):
        return {}
    try:
        with open(RM_CFG_F, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except:
        return {}

def save_rm_config(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RM_CFG_F, "w", encoding="utf-8-sig") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ──────────────────────────────────────────────────────
#  ★ v2.2.1 修正：load_carousel / save_carousel
#  carousel.json 格式：{"cards": [ {...}, {...}, ... ]}
#  load 回傳 list（cards 陣列）
#  save 以 {"cards": [...]} 包裝寫回
# ──────────────────────────────────────────────────────
def load_carousel():
    """
    讀取 carousel.json。
    支援兩種格式：
      - 新格式（正確）：{"cards": [...]}   → 回傳 cards list
      - 舊格式（相容）：[...]              → 直接回傳 list
    任何例外皆回傳空 list。
    """
    if not os.path.exists(CAROUSEL_F):
        print("[WARN] carousel.json 不存在，回傳空卡片")
        return []
    try:
        with open(CAROUSEL_F, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)

        # 新格式：{"cards": [...]}
        if isinstance(raw, dict):
            cards = raw.get("cards", [])
            if not isinstance(cards, list):
                print(f"[ERROR] carousel.json 'cards' 不是 list: {type(cards)}")
                return []
            print(f"[OK] 載入 {len(cards)} 張輪播卡片（dict 格式）")
            return cards

        # 舊格式相容：直接是 list
        if isinstance(raw, list):
            print(f"[OK] 載入 {len(raw)} 張輪播卡片（list 格式，舊版相容）")
            return raw

        print(f"[ERROR] carousel.json 格式無法識別: {type(raw)}")
        return []

    except json.JSONDecodeError as e:
        print(f"[ERROR] carousel.json JSON 解析失敗: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] 載入 carousel.json 失敗: {e}")
        return []


def save_carousel(cards):
    """
    以 {"cards": [...]} 格式寫回 carousel.json。
    webhook_server.py 使用 carousel_data.get("cards", []) 讀取，
    必須保持此格式。
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = {"cards": cards}
    with open(CAROUSEL_F, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[OK] carousel.json 已儲存，共 {len(cards)} 張卡片")


# ════════════════════════════════════════════════════════
#  主應用程式
# ════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("維康醫療用品 LINE OA 總控管理系統")
        self.geometry("1400x820")
        self.configure(bg=C["header_bg"])
        self.minsize(1100, 650)

        # 載入資料
        self.stores     = load_stores()
        self.rm_config  = load_rm_config()
        self.carousel   = load_carousel()   # ← 現在保證是 list
        self._cur_card_idx = 0
        self.cur_page   = None
        self.sel_store  = None

        self._build_ui()
        self._nav_to("overview")
        self._tick()

    # ── UI 骨架 ─────────────────────────────────────────
    def _build_ui(self):
        hdr = tk.Frame(self, bg=C["header_bg"], height=55)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="維康醫療用品", font=("微軟正黑體",16,"bold"),
                 bg=C["header_bg"], fg="white").pack(side="left", padx=20, pady=12)
        tk.Label(hdr, text="LINE OA 總控管理系統", font=("微軟正黑體",12),
                 bg=C["header_bg"], fg=C["teal"]).pack(side="left", pady=12)
        self.lbl_time = tk.Label(hdr, text="", font=("Consolas",11),
                                 bg=C["header_bg"], fg="#aaaaaa")
        self.lbl_time.pack(side="right", padx=20)

        body = tk.Frame(self, bg=C["main_bg"])
        body.pack(fill="both", expand=True)

        self._build_sidebar(body)

        self.content = tk.Frame(body, bg=C["main_bg"])
        self.content.pack(side="left", fill="both", expand=True)

    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=C["sidebar_bg"], width=120)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        nav_items = [
            ("功能選單","menu"),
            ("門市總覽","overview"),
            ("Rich Menu","richmenu"),
            ("輪播卡片","carousel"),
            ("Webhook","webhook"),
            ("操作日誌","log"),
        ]
        icons = {"menu":"☰","overview":"🏪","richmenu":"▦",
                 "carousel":"🎠","webhook":"🔗","log":"📋"}
        self.sb_btns = {}
        for name, key in nav_items:
            f = tk.Frame(sb, bg=C["sidebar_bg"], cursor="hand2")
            f.pack(fill="x")
            lbl = tk.Label(f, text=f"{icons.get(key,'')} {name}",
                           font=("微軟正黑體",10), bg=C["sidebar_bg"],
                           fg=C["sidebar_fg"], pady=14, padx=10,
                           justify="center", anchor="w")
            lbl.pack(fill="x")
            for w in (f, lbl):
                w.bind("<Button-1>", lambda e, k=key: self._nav_to(k))
                w.bind("<Enter>",    lambda e, w=lbl: w.config(fg="white"))
                w.bind("<Leave>",    lambda e, w=lbl, k=key:
                       w.config(fg="white" if self.cur_page==k else C["sidebar_fg"]))
            self.sb_btns[key] = (f, lbl)

        # ★ v2.2.1 版本號
        tk.Label(sb, text="v2.3.0", font=("Consolas",8),
                 bg=C["sidebar_bg"], fg="#555").pack(side="bottom", pady=6)

    def _nav_to(self, key):
        self.cur_page = key
        for k,(f,lbl) in self.sb_btns.items():
            if k == key:
                f.config(bg=C["sidebar_sel"])
                lbl.config(bg=C["sidebar_sel"], fg="white")
            else:
                f.config(bg=C["sidebar_bg"])
                lbl.config(bg=C["sidebar_bg"], fg=C["sidebar_fg"])
        for w in self.content.winfo_children():
            w.destroy()
        pages = {
            "menu"     : self._page_menu,
            "overview" : self._page_overview,
            "richmenu" : self._page_richmenu,
            "carousel" : self._page_carousel,
            "webhook"  : self._page_webhook,
            "log"      : self._page_log,
        }
        pages.get(key, self._page_overview)()

    def _tick(self):
        self.lbl_time.config(text=datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.after(1000, self._tick)

    # ════════════════════════════════════════════════════
    #  頁面：功能選單
    # ════════════════════════════════════════════════════
    def _page_menu(self):
        f = tk.Frame(self.content, bg=C["main_bg"])
        f.pack(fill="both", expand=True, padx=30, pady=30)
        tk.Label(f, text="功能選單", font=("微軟正黑體",18,"bold"),
                 bg=C["main_bg"], fg=C["text"]).pack(anchor="w", pady=(0,20))
        btns = [
            ("🏪  門市總覽",       C["teal"],   "overview"),
            ("▦   Rich Menu 管理", C["blue"],   "richmenu"),
            ("🎠  輪播卡片設定",   C["purple"], "carousel"),
            ("🔗  Webhook 設定",   C["orange"], "webhook"),
            ("📋  操作日誌",       C["dark"],   "log"),
        ]
        for txt, col, key in btns:
            tk.Button(f, text=txt, font=("微軟正黑體",13),
                      bg=col, fg="white", relief="flat",
                      activebackground=col, cursor="hand2",
                      width=28, pady=10,
                      command=lambda k=key: self._nav_to(k)
                      ).pack(pady=6, anchor="w")

    # ════════════════════════════════════════════════════
    #  頁面：門市總覽
    # ════════════════════════════════════════════════════
    def _page_overview(self):
        f = tk.Frame(self.content, bg=C["main_bg"])
        f.pack(fill="both", expand=True, padx=30, pady=20)

        tk.Label(f, text="門市總覽", font=("微軟正黑體",18,"bold"),
                 bg=C["main_bg"], fg=C["text"]).pack(anchor="w", pady=(0,10))

        cols = ("代碼","名稱","Channel ID","Rich Menu ID","狀態")
        tree_frame = tk.Frame(f, bg=C["main_bg"])
        tree_frame.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=C["card_bg"],
                        foreground=C["text"],
                        rowheight=26,
                        fieldbackground=C["card_bg"],
                        font=("微軟正黑體",10))
        style.configure("Treeview.Heading",
                        background=C["teal"],
                        foreground="white",
                        font=("微軟正黑體",10,"bold"))
        style.map("Treeview", background=[("selected","#b2dfdb")])

        tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                            yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.config(command=tree.yview)
        hsb.config(command=tree.xview)

        widths = {"代碼":60,"名稱":230,"Channel ID":180,"Rich Menu ID":260,"狀態":70}
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=widths.get(c,120), anchor="w")

        tree.pack(fill="both", expand=True)

        print(f"[DEBUG] _page_overview: stores 筆數 = {len(self.stores)}")
        for s in self.stores:
            print(f"[DEBUG]   store = {s}")
            tree.insert("", "end", values=(
                s.get("id",""),
                s.get("name",""),
                s.get("channel_id", s.get("channel_access_token","")[:20]+"..."
                      if s.get("channel_access_token","") else ""),
                s.get("rich_menu_id",""),
                s.get("status",""),
            ))

        stat = tk.Frame(f, bg=C["main_bg"])
        stat.pack(fill="x", pady=(8,0))
        total  = len(self.stores)
        active = sum(1 for s in self.stores if s.get("status","").lower()=="active")
        tk.Label(stat,
                 text=f"共 {total} 間門市　|　已啟用: {active}　|　未啟用: {total-active}",
                 font=("微軟正黑體",10), bg=C["main_bg"], fg=C["sub"]).pack(anchor="w")

    # ════════════════════════════════════════════════════
    #  頁面：Rich Menu  ← 完全未動，與 v2.2.0 一致
    # ════════════════════════════════════════════════════
    def _page_richmenu(self):
        outer = tk.Frame(self.content, bg=C["main_bg"])
        outer.pack(fill="both", expand=True)

        left = tk.LabelFrame(outer, text="門市選擇", bg=C["main_bg"],
                              font=("微軟正黑體",10,"bold"), fg=C["text"],
                              padx=6, pady=6)
        left.pack(side="left", fill="y", padx=(16,0), pady=16)

        btn_row = tk.Frame(left, bg=C["main_bg"])
        btn_row.pack(fill="x", pady=(0,4))
        tk.Button(btn_row, text="☑ 全選", font=("微軟正黑體",9),
                  bg=C["teal"], fg="white", relief="flat", cursor="hand2",
                  command=lambda: self._rm_select_all(lb, True)
                  ).pack(side="left", padx=2)
        tk.Button(btn_row, text="☐ 取消", font=("微軟正黑體",9),
                  bg=C["sub"], fg="white", relief="flat", cursor="hand2",
                  command=lambda: self._rm_select_all(lb, False)
                  ).pack(side="left", padx=2)

        lb = tk.Listbox(left, selectmode="extended", width=28, height=25,
                        font=("微軟正黑體",10), bg=C["card_bg"],
                        selectbackground=C["teal"], selectforeground="white",
                        activestyle="none", relief="flat", borderwidth=1,
                        highlightthickness=1, highlightcolor=C["border"])
        lb.pack(fill="both", expand=True)

        for s in self.stores:
            lb.insert("end", f"{s.get('id','')}  {s.get('name','')[:14]}")

        lb.bind("<<ListboxSelect>>", lambda e: self._rm_load_store(lb))

        right = tk.LabelFrame(outer, text="Rich Menu 設定", bg=C["main_bg"],
                               font=("微軟正黑體",10,"bold"), fg=C["text"],
                               padx=10, pady=10)
        right.pack(side="left", fill="both", expand=True, padx=16, pady=16)

        self.rm_hint = tk.Label(right, text="🔥 請點左側門市名稱載入設定",
                                font=("微軟正黑體",11), bg=C["main_bg"],
                                fg=C["orange"])
        self.rm_hint.pack(anchor="w", pady=(0,8))

        img_row = tk.Frame(right, bg=C["main_bg"])
        img_row.pack(fill="x", pady=4)
        tk.Label(img_row, text="選單圖片路徑：", font=("微軟正黑體",10),
                 bg=C["main_bg"], fg=C["text"]).pack(side="left")
        self.rm_img_var = tk.StringVar(value="assets/richmenu.png")
        tk.Entry(img_row, textvariable=self.rm_img_var, width=40,
                 font=("微軟正黑體",10)).pack(side="left", padx=4)
        tk.Button(img_row, text="瀏覽", font=("微軟正黑體",9),
                  bg=C["sub"], fg="white", relief="flat", cursor="hand2",
                  command=self._rm_browse_img).pack(side="left")

        blk_frame = tk.LabelFrame(right,
                                   text="區塊動作設定（B1 = 輪播觸發，固定不可改）",
                                   bg=C["main_bg"], font=("微軟正黑體",9), fg=C["sub"])
        blk_frame.pack(fill="x", pady=8)

        self.rm_type_vars   = {}
        self.rm_action_vars = {}
        for i in range(2, 7):
            row = tk.Frame(blk_frame, bg=C["main_bg"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"B{i} 類型：", font=("微軟正黑體",10),
                     bg=C["main_bg"], fg=C["text"], width=8).pack(side="left")
            t_var = tk.StringVar(value="uri")
            self.rm_type_vars[i] = t_var
            ttk.Combobox(row, textvariable=t_var,
                         values=["uri","message","postback"],
                         width=10, state="readonly").pack(side="left")
            a_var = tk.StringVar()
            self.rm_action_vars[i] = a_var
            tk.Entry(row, textvariable=a_var, width=55,
                     font=("微軟正黑體",10)).pack(side="left", padx=4)
            tk.Label(row, text="填入 https://... 或文字",
                     font=("微軟正黑體",8), bg=C["main_bg"],
                     fg=C["sub"]).pack(side="left")

        btn_area = tk.Frame(right, bg=C["main_bg"])
        btn_area.pack(fill="x", pady=10)
        actions = [
            ("🔍 查詢選單", C["dark"],   self._rm_query),
            ("＋ 建立選單", C["teal"],   self._rm_create),
            ("⬆ 上傳圖片", C["blue"],   self._rm_upload_img),
            ("★ 設為預設", C["purple"], self._rm_set_default),
            ("🗑 刪除選單", C["red"],    self._rm_delete),
            ("⚡ 一鍵部署", C["orange"], self._rm_deploy_all),
            ("💾 儲存設定", C["teal"],   self._rm_save_cfg),
        ]
        for txt, col, cmd in actions:
            tk.Button(btn_area, text=txt, font=("微軟正黑體",9),
                      bg=col, fg="white", relief="flat", cursor="hand2",
                      padx=8, pady=6,
                      command=cmd).pack(side="left", padx=3)

        res_frame = tk.LabelFrame(right, text="執行結果",
                                   bg=C["main_bg"], font=("微軟正黑體",9))
        res_frame.pack(fill="both", expand=True, pady=(6,0))
        self.rm_log = tk.Text(res_frame, height=8, bg=C["log_bg"],
                              fg=C["log_fg"], font=("Consolas",9),
                              relief="flat", state="disabled")
        self.rm_log.pack(fill="both", expand=True, padx=4, pady=4)

        self._rm_lb_ref = lb

    def _rm_select_all(self, lb, select):
        if select:
            lb.select_set(0, "end")
        else:
            lb.select_clear(0, "end")

    def _rm_browse_img(self):
        p = filedialog.askopenfilename(
            title="選擇 Rich Menu 圖片",
            filetypes=[("PNG/JPG","*.png *.jpg *.jpeg"),("All","*.*")])
        if p:
            self.rm_img_var.set(p)

    def _rm_load_store(self, lb):
        sel = lb.curselection()
        if not sel:
            return
        idx = sel[-1]
        if idx >= len(self.stores):
            return
        store = self.stores[idx]
        sid   = store.get("id","")
        self.sel_store = store
        self.rm_hint.config(text=f"✅ 已選：{sid} {store.get('name','')}", fg=C["teal"])
        cfg = self.rm_config.get(sid, {})
        blocks = cfg.get("blocks", {})
        self.rm_img_var.set(cfg.get("image_url","assets/richmenu.png"))
        for i in range(2, 7):
            bdata = blocks.get(str(i), {})
            self.rm_type_vars[i].set(bdata.get("type","uri"))
            self.rm_action_vars[i].set(bdata.get("action",""))

    def _rm_get_selected_stores(self):
        sel = self._rm_lb_ref.curselection()
        return [self.stores[i] for i in sel if i < len(self.stores)]

    def _rm_log_msg(self, msg):
        self.rm_log.config(state="normal")
        self.rm_log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.rm_log.see("end")
        self.rm_log.config(state="disabled")

    def _rm_save_cfg(self):
        if not self.sel_store:
            messagebox.showwarning("提示","請先點選左側門市")
            return
        sid = self.sel_store.get("id","")
        if sid not in self.rm_config:
            self.rm_config[sid] = {}
        self.rm_config[sid]["image_url"] = self.rm_img_var.get()
        blocks = {"1": {"type":"postback","action":"show_carousel"}}
        for i in range(2, 7):
            blocks[str(i)] = {
                "type"  : self.rm_type_vars[i].get(),
                "action": self.rm_action_vars[i].get()
            }
        self.rm_config[sid]["blocks"] = blocks
        save_rm_config(self.rm_config)
        self._rm_log_msg(f"[{sid}] 設定已儲存")
        messagebox.showinfo("完成",f"{sid} 設定已儲存")

    def _make_rm_body(self, sid):
        cfg    = self.rm_config.get(sid, {})
        blocks = cfg.get("blocks", {})
        areas  = []
        for i, layout in enumerate(BLOCKS_LAYOUT, 1):
            row = 0 if i <= 3 else 1
            b   = blocks.get(str(i), {})
            btype   = b.get("type","uri")
            baction = b.get("action","")
            if btype == "uri":
                action = {"type":"uri","uri": baction or "https://www.wellcare.com.tw"}
            elif btype == "message":
                action = {"type":"message","text": baction or sid}
            else:
                action = {"type":"postback","data": baction or "show_carousel",
                          "displayText":"查看最新優惠"}
            areas.append({
                "bounds":{"x": layout["x"],
                          "y": BLOCK_Y + row * BLOCK_H,
                          "width": layout["w"], "height": BLOCK_H},
                "action": action
            })
        return {
            "size":   {"width": RM_W, "height": RM_H},
            "selected": True,
            "name":   cfg.get("menu_name", f"{sid}主選單"),
            "chatBarText": "點我開啟選單",
            "areas":  areas
        }

    def _rm_query(self):
        stores = self._rm_get_selected_stores()
        if not stores:
            messagebox.showwarning("提示","請先勾選門市")
            return
        def run():
            for s in stores:
                token = s.get("channel_access_token","")
                sid   = s.get("id","")
                if not token:
                    self._rm_log_msg(f"[{sid}] 無 token，跳過")
                    continue
                try:
                    r = requests.get(
                        "https://api.line.me/v2/bot/richmenu/list",
                        headers={"Authorization":f"Bearer {token}"}, timeout=10)
                    data  = r.json()
                    menus = data.get("richmenus",[])
                    self._rm_log_msg(f"[{sid}] 查到 {len(menus)} 個 Rich Menu")
                    for m in menus:
                        self._rm_log_msg(f"  ├ {m.get('richMenuId','')}  {m.get('name','')}")
                except Exception as e:
                    self._rm_log_msg(f"[{sid}] 查詢失敗: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _rm_create(self):
        stores = self._rm_get_selected_stores()
        if not stores:
            messagebox.showwarning("提示","請先勾選門市")
            return
        def run():
            for s in stores:
                token = s.get("channel_access_token","")
                sid   = s.get("id","")
                if not token:
                    self._rm_log_msg(f"[{sid}] 無 token，跳過")
                    continue
                body = self._make_rm_body(sid)
                try:
                    r = requests.post(
                        "https://api.line.me/v2/bot/richmenu",
                        headers={"Authorization":f"Bearer {token}",
                                 "Content-Type":"application/json"},
                        json=body, timeout=15)
                    if r.status_code == 200:
                        rm_id = r.json().get("richMenuId","")
                        self._rm_log_msg(f"[{sid}] 建立成功: {rm_id}")
                        if sid not in self.rm_config:
                            self.rm_config[sid] = {}
                        self.rm_config[sid]["rich_menu_id"] = rm_id
                        save_rm_config(self.rm_config)
                    else:
                        self._rm_log_msg(f"[{sid}] 建立失敗 {r.status_code}: {r.text[:200]}")
                except Exception as e:
                    self._rm_log_msg(f"[{sid}] 例外: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _rm_upload_img(self):
        stores = self._rm_get_selected_stores()
        if not stores:
            messagebox.showwarning("提示","請先勾選門市")
            return
        img_path = self.rm_img_var.get()
        if not os.path.exists(img_path):
            messagebox.showerror("錯誤",f"圖片不存在:\n{img_path}")
            return
        def run():
            for s in stores:
                token = s.get("channel_access_token","")
                sid   = s.get("id","")
                rm_id = self.rm_config.get(sid,{}).get("rich_menu_id","")
                if not token or not rm_id:
                    self._rm_log_msg(f"[{sid}] 缺少 token 或 rich_menu_id，跳過")
                    continue
                try:
                    with open(img_path,"rb") as f:
                        ct = "image/png" if img_path.lower().endswith(".png") else "image/jpeg"
                        r  = requests.post(
                            f"https://api-data.line.me/v2/bot/richmenu/{rm_id}/content",
                            headers={"Authorization":f"Bearer {token}",
                                     "Content-Type": ct},
                            data=f.read(), timeout=30)
                    if r.status_code == 200:
                        self._rm_log_msg(f"[{sid}] 圖片上傳成功")
                    else:
                        self._rm_log_msg(f"[{sid}] 上傳失敗 {r.status_code}: {r.text[:200]}")
                except Exception as e:
                    self._rm_log_msg(f"[{sid}] 例外: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _rm_set_default(self):
        stores = self._rm_get_selected_stores()
        if not stores:
            messagebox.showwarning("提示","請先勾選門市")
            return
        def run():
            for s in stores:
                token = s.get("channel_access_token","")
                sid   = s.get("id","")
                rm_id = self.rm_config.get(sid,{}).get("rich_menu_id","")
                if not token or not rm_id:
                    self._rm_log_msg(f"[{sid}] 缺少 token 或 rich_menu_id，跳過")
                    continue
                try:
                    r = requests.post(
                        f"https://api.line.me/v2/bot/user/all/richmenu/{rm_id}",
                        headers={"Authorization":f"Bearer {token}"}, timeout=10)
                    if r.status_code == 200:
                        self._rm_log_msg(f"[{sid}] 設為預設成功")
                    else:
                        self._rm_log_msg(f"[{sid}] 失敗 {r.status_code}: {r.text[:200]}")
                except Exception as e:
                    self._rm_log_msg(f"[{sid}] 例外: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _rm_delete(self):
        stores = self._rm_get_selected_stores()
        if not stores:
            messagebox.showwarning("提示","請先勾選門市")
            return
        if not messagebox.askyesno("確認","確定刪除所選門市的 Rich Menu？"):
            return
        def run():
            for s in stores:
                token = s.get("channel_access_token","")
                sid   = s.get("id","")
                rm_id = self.rm_config.get(sid,{}).get("rich_menu_id","")
                if not token or not rm_id:
                    self._rm_log_msg(f"[{sid}] 缺少資訊，跳過")
                    continue
                try:
                    r = requests.delete(
                        f"https://api.line.me/v2/bot/richmenu/{rm_id}",
                        headers={"Authorization":f"Bearer {token}"}, timeout=10)
                    if r.status_code == 200:
                        self._rm_log_msg(f"[{sid}] 刪除成功")
                    else:
                        self._rm_log_msg(f"[{sid}] 失敗 {r.status_code}: {r.text[:200]}")
                except Exception as e:
                    self._rm_log_msg(f"[{sid}] 例外: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _rm_deploy_all(self):
        stores = self._rm_get_selected_stores()
        if not stores:
            messagebox.showwarning("提示","請先勾選門市")
            return
        img_path = self.rm_img_var.get()
        if not os.path.exists(img_path):
            messagebox.showerror("錯誤",f"圖片不存在:\n{img_path}")
            return
        self._rm_log_msg(f"=== 一鍵部署開始：{len(stores)} 間門市 ===")
        def run():
            for s in stores:
                token = s.get("channel_access_token","")
                sid   = s.get("id","")
                if not token:
                    self._rm_log_msg(f"[{sid}] 無 token，跳過")
                    continue
                body = self._make_rm_body(sid)
                try:
                    r = requests.post(
                        "https://api.line.me/v2/bot/richmenu",
                        headers={"Authorization":f"Bearer {token}",
                                 "Content-Type":"application/json"},
                        json=body, timeout=15)
                    if r.status_code != 200:
                        self._rm_log_msg(f"[{sid}] 建立失敗: {r.text[:100]}")
                        continue
                    rm_id = r.json().get("richMenuId","")
                    self._rm_log_msg(f"[{sid}] ① 建立 OK: {rm_id}")
                    if sid not in self.rm_config:
                        self.rm_config[sid] = {}
                    self.rm_config[sid]["rich_menu_id"] = rm_id
                    save_rm_config(self.rm_config)
                except Exception as e:
                    self._rm_log_msg(f"[{sid}] 建立例外: {e}")
                    continue
                try:
                    with open(img_path,"rb") as f:
                        ct = "image/png" if img_path.lower().endswith(".png") else "image/jpeg"
                        r2 = requests.post(
                            f"https://api-data.line.me/v2/bot/richmenu/{rm_id}/content",
                            headers={"Authorization":f"Bearer {token}","Content-Type":ct},
                            data=f.read(), timeout=30)
                    if r2.status_code == 200:
                        self._rm_log_msg(f"[{sid}] ② 上傳圖片 OK")
                    else:
                        self._rm_log_msg(f"[{sid}] ② 上傳失敗: {r2.text[:100]}")
                        continue
                except Exception as e:
                    self._rm_log_msg(f"[{sid}] 上傳例外: {e}")
                    continue
                try:
                    r3 = requests.post(
                        f"https://api.line.me/v2/bot/user/all/richmenu/{rm_id}",
                        headers={"Authorization":f"Bearer {token}"}, timeout=10)
                    if r3.status_code == 200:
                        self._rm_log_msg(f"[{sid}] ③ 設預設 OK ✅")
                    else:
                        self._rm_log_msg(f"[{sid}] ③ 設預設失敗: {r3.text[:100]}")
                except Exception as e:
                    self._rm_log_msg(f"[{sid}] 設預設例外: {e}")
            self._rm_log_msg("=== 一鍵部署完畢 ===")
        threading.Thread(target=run, daemon=True).start()

    # ════════════════════════════════════════════════════
    #  頁面：輪播卡片  ← ★ v2.3.0 Image Carousel Template
    # ════════════════════════════════════════════════════
    def _page_carousel(self):
        parent = self.content
        for w in parent.winfo_children():
            w.destroy()

        tk.Label(parent, text="🖼️ 輪播卡片管理 (Image Carousel Template)",
                 font=("微軟正黑體", 16, "bold"),
                 bg=C["main_bg"], fg=C["text"]).pack(pady=(20, 10))

        carousel_path = os.path.join(BASE_DIR, "data", "carousel.json")
        try:
            with open(carousel_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            cards = data.get("cards", [])
        except Exception as e:
            messagebox.showerror("讀取失敗", str(e))
            return

        outer = tk.Frame(parent, bg=C["main_bg"])
        outer.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        canvas    = tk.Canvas(outer, bg=C["main_bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        sf        = tk.Frame(canvas, bg=C["main_bg"])
        sf.bind("<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        entries = []

        for i, card in enumerate(cards):
            frm = tk.LabelFrame(sf, text=f"Card {i+1}",
                                font=("微軟正黑體", 11, "bold"),
                                bg=C["card_bg"], fg=C["dark"],
                                padx=10, pady=8)
            frm.pack(fill="x", padx=10, pady=8)

            tk.Label(frm, text="id :", bg=C["card_bg"], width=12, anchor="w",
                     font=("微軟正黑體", 10)).grid(row=0, column=0, sticky="w")
            id_var = tk.StringVar(value=card.get("id", ""))
            tk.Entry(frm, textvariable=id_var, width=40,
                     font=("微軟正黑體", 10)).grid(row=0, column=1, sticky="w", pady=2)

            tk.Label(frm, text="title :", bg=C["card_bg"], width=12, anchor="w",
                     font=("微軟正黑體", 10)).grid(row=1, column=0, sticky="w")
            title_var = tk.StringVar(value=card.get("title", ""))
            tk.Entry(frm, textvariable=title_var, width=40,
                     font=("微軟正黑體", 10)).grid(row=1, column=1, sticky="w", pady=2)

            tk.Label(frm, text="imageUrl :", bg=C["card_bg"], width=12, anchor="w",
                     font=("微軟正黑體", 10)).grid(row=2, column=0, sticky="w")
            url_var = tk.StringVar(value=card.get("imageUrl", ""))
            tk.Entry(frm, textvariable=url_var, width=65,
                     font=("微軟正黑體", 10)).grid(row=2, column=1, sticky="w", pady=2)

            tk.Label(frm, text="reply_text :", bg=C["card_bg"], width=12, anchor="nw",
                     font=("微軟正黑體", 10)).grid(row=3, column=0, sticky="nw", pady=(4, 0))
            rt = tk.Text(frm, width=65, height=4, font=("微軟正黑體", 10))
            rt.grid(row=3, column=1, sticky="w", pady=2)
            rt.insert("1.0", card.get("reply_text", ""))

            entries.append((id_var, title_var, url_var, rt))

        def save_carousel():
            new_cards = []
            for id_v, title_v, url_v, rt_w in entries:
                new_cards.append({
                    "id":         id_v.get().strip(),
                    "title":      title_v.get().strip(),
                    "imageUrl":   url_v.get().strip(),
                    "reply_text": rt_w.get("1.0", "end").strip()
                })
            try:
                with open(carousel_path, "w", encoding="utf-8") as f:
                    json.dump({"cards": new_cards}, f,
                              ensure_ascii=False, indent=2)
                messagebox.showinfo("成功",
                    f"carousel.json 已儲存！共 {len(new_cards)} 張卡片")
            except Exception as e:
                messagebox.showerror("儲存失敗", str(e))

        tk.Button(parent, text="💾  儲存 carousel.json",
                  command=save_carousel,
                  bg=C["teal"], fg="white",
                  font=("微軟正黑體", 12, "bold"),
                  padx=20, pady=8, relief="flat",
                  cursor="hand2").pack(pady=12)
    # ════════════════════════════════════════════════════
    #  頁面：Webhook
    # ════════════════════════════════════════════════════
    def _page_webhook(self):
        f = tk.Frame(self.content, bg=C["main_bg"])
        f.pack(fill="both", expand=True, padx=30, pady=20)
        tk.Label(f, text="Webhook 設定", font=("微軟正黑體",18,"bold"),
                 bg=C["main_bg"], fg=C["text"]).pack(anchor="w", pady=(0,6))
        tk.Label(f,
                 text="請將以下 URL 填入各門市的 LINE Developers Console"
                      " → Messaging API → Webhook URL",
                 font=("微軟正黑體",10), bg=C["main_bg"], fg=C["sub"]
                 ).pack(anchor="w", pady=(0,10))

        txt = tk.Text(f, font=("Consolas",10), bg=C["card_bg"],
                      fg=C["text"], relief="solid", borderwidth=1)
        txt.pack(fill="both", expand=True)

        for s in self.stores:
            sid = s.get("id","")
            url = f"{WEBHOOK_BASE}/{sid}"
            txt.insert("end", f"{sid}  {s.get('name','')}\n")
            txt.insert("end", f"  → {url}\n\n")
        txt.config(state="disabled")

    # ════════════════════════════════════════════════════
    #  頁面：操作日誌
    # ════════════════════════════════════════════════════
    def _page_log(self):
        f = tk.Frame(self.content, bg=C["main_bg"])
        f.pack(fill="both", expand=True, padx=30, pady=20)
        tk.Label(f, text="操作日誌", font=("微軟正黑體",18,"bold"),
                 bg=C["main_bg"], fg=C["text"]).pack(anchor="w", pady=(0,10))
        log = tk.Text(f, font=("Consolas",10), bg=C["log_bg"],
                      fg=C["log_fg"], relief="flat", state="disabled")
        log.pack(fill="both", expand=True)
        log.config(state="normal")
        log.insert("end",
                   f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 系統啟動\n")
        log.insert("end", f"[INFO] 載入門市數: {len(self.stores)}\n")
        log.insert("end", f"[INFO] 輪播卡片數: {len(self.carousel)}\n")
        log.config(state="disabled")


# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()
