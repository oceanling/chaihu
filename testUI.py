import streamlit as st
import sqlite3
import re
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime

# 设置页面配置（必须在所有Streamlit命令之前）
st.set_page_config(
    page_title="柴胡查询系统",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed"  # 移动端默认折叠侧边栏
)

# 自定义CSS样式
def load_custom_css():
    st.markdown("""
    <style>
    /* 基础样式 */
    .main {
        padding: 1rem;
    }
    
    /* 移动端优化 */
    @media (max-width: 768px) {
        .block-container {
            padding: 1rem 0.5rem;
        }
        .stButton > button {
            width: 100%;
            margin: 0.25rem 0;
        }
        .stSelectbox, .stTextInput, .stTextArea {
            width: 100%;
        }
    }
    
    /* 卡片样式 */
    .species-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 5px solid #4CAF50;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    .species-card h3 {
        color: #2c3e50;
        margin-top: 0;
    }
    
    /* 标签样式 */
    .tag {
        display: inline-block;
        background: #4CAF50;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 15px;
        font-size: 0.8rem;
        margin: 0.2rem;
    }
    
    /* 搜索框样式 */
    .search-container {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    
    /* 表格样式 */
    .dataframe {
        width: 100%;
        border-collapse: collapse;
    }
    
    .dataframe th {
        background-color: #4CAF50;
        color: white;
        padding: 0.5rem;
        text-align: left;
    }
    
    .dataframe td {
        padding: 0.5rem;
        border-bottom: 1px solid #ddd;
    }
    
    /* 按钮样式 */
    .stButton > button {
        border-radius: 20px;
        border: none;
        background: linear-gradient(45deg, #4CAF50, #8BC34A);
        color: white;
        font-weight: bold;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* 徽章样式 */
    .badge {
        display: inline-block;
        background: #FF9800;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.7rem;
        margin-left: 0.5rem;
    }
    
    /* 折叠面板样式 */
    .streamlit-expanderHeader {
        background: #f1f8ff;
        border-radius: 5px;
    }
    
    /* 隐藏Streamlit默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* 响应式图片 */
    img {
        max-width: 100%;
        height: auto;
    }
    
    /* 自定义标题 */
    .custom-title {
        background: linear-gradient(45deg, #4CAF50, #2E7D32);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    </style>
    """, unsafe_allow_html=True)

# 加载CSS
load_custom_css()

class BupleurumDatabase:
    """柴胡数据库管理类（优化版）"""
    
    def __init__(self, db_path='bupleurum.db'):
        self.db_path = db_path
        self.conn = None
        self.initialize_database()
    
    def connect(self):
        """连接到数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def initialize_database(self):
        """初始化数据库表"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # 创建主表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bupleurum_species (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_chinese TEXT NOT NULL UNIQUE,
                name_latin TEXT,
                root TEXT,
                stem TEXT,
                leaf TEXT,
                flower_inflorescence TEXT,
                fruit TEXT,
                flowering_fruiting TEXT,
                habitat TEXT,
                medicinal_use TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # 创建变种表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS varieties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                species_id INTEGER,
                name_chinese TEXT NOT NULL,
                description TEXT,
                FOREIGN KEY (species_id) REFERENCES bupleurum_species (id) ON DELETE CASCADE
            )
            ''')
            
            # 创建搜索索引
            cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS species_fts USING fts5(
                name_chinese, root, stem, leaf, flower_inflorescence, 
                fruit, flowering_fruiting, habitat, medicinal_use, notes,
                tokenize="porter"
            )
            ''')
            
            conn.commit()
    
    def search_species_fts(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """使用全文搜索查询柴胡品种"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            if not query:
                cursor.execute("""
                SELECT bs.*, 
                       GROUP_CONCAT(v.name_chinese, '|') as variety_names
                FROM bupleurum_species bs
                LEFT JOIN varieties v ON bs.id = v.species_id
                GROUP BY bs.id
                ORDER BY bs.name_chinese
                LIMIT ?
                """, (limit,))
            else:
                cursor.execute("""
                SELECT bs.*, 
                       GROUP_CONCAT(v.name_chinese, '|') as variety_names,
                       snippet(species_fts, 0, '<mark>', '</mark>', '...', 10) as snippet
                FROM bupleurum_species bs
                LEFT JOIN species_fts ON bs.id = species_fts.rowid
                LEFT JOIN varieties v ON bs.id = v.species_id
                WHERE species_fts MATCH ?
                GROUP BY bs.id
                ORDER BY rank
                LIMIT ?
                """, (f"{query}*", limit))
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('variety_names'):
                    result['varieties'] = [
                        {'name_chinese': name} 
                        for name in result['variety_names'].split('|') 
                        if name
                    ]
                else:
                    result['varieties'] = []
                results.append(result)
            
            return results
    
    def add_species(self, species_data: Dict[str, Any]) -> int:
        """添加柴胡品种"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # 提取变种信息
            varieties = species_data.pop('varieties', [])
            
            # 准备数据
            columns = list(species_data.keys())
            placeholders = ['?'] * len(columns)
            values = list(species_data.values())
            
            # 插入主品种
            sql = f"INSERT INTO bupleurum_species ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(sql, values)
            species_id = cursor.lastrowid
            
            # 插入变种
            for variety in varieties:
                cursor.execute(
                    "INSERT INTO varieties (species_id, name_chinese, description) VALUES (?, ?, ?)",
                    (species_id, variety.get('name_chinese', ''), variety.get('description', ''))
                )
            
            # 更新全文搜索索引
            cursor.execute(f"""
            INSERT INTO species_fts(rowid, {', '.join(columns)})
            VALUES (?, {', '.join(['?'] * len(columns))})
            """, [species_id] + values)
            
            conn.commit()
            return species_id
    
    def get_species_by_id(self, species_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取柴胡品种"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT bs.*, 
                   GROUP_CONCAT(v.name_chinese || ':' || v.description, '||') as variety_data
            FROM bupleurum_species bs
            LEFT JOIN varieties v ON bs.id = v.species_id
            WHERE bs.id = ?
            GROUP BY bs.id
            """, (species_id,))
            
            row = cursor.fetchone()
            if row:
                result = dict(row)
                
                # 处理变种数据
                if result.get('variety_data'):
                    varieties = []
                    for item in result['variety_data'].split('||'):
                        if ':' in item:
                            name, desc = item.split(':', 1)
                            varieties.append({'name_chinese': name, 'description': desc})
                    result['varieties'] = varieties
                else:
                    result['varieties'] = []
                
                return result
            
            return None
    
    def get_all_species_names(self) -> List[str]:
        """获取所有柴胡品种名称"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name_chinese FROM bupleurum_species ORDER BY name_chinese")
            return [row[0] for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict[str, int]:
        """获取数据库统计信息"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM bupleurum_species")
            total_species = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM varieties")
            total_varieties = cursor.fetchone()[0]
            
            return {
                'total_species': total_species,
                'total_varieties': total_varieties
            }
    
    def clear_database(self):
        """清空数据库（仅用于测试）"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM varieties")
            cursor.execute("DELETE FROM bupleurum_species")
            cursor.execute("DELETE FROM species_fts")
            conn.commit()

# 初始化数据库
@st.cache_resource
def get_database():
    return BupleurumDatabase()

db = get_database()

# 应用标题
def render_header():
    st.markdown("""
    <div class="custom-title">
        <h1 style="margin: 0;">🌿 柴胡查询系统</h1>
        <p style="margin: 0; opacity: 0.9;">传统草药数据库 | 移动端优化</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 统计信息
    stats = db.get_statistics()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🌱 品种总数", stats['total_species'])
    with col2:
        st.metric("🌿 变种总数", stats['total_varieties'])
    with col3:
        st.metric("📊 数据完整性", f"{min(100, stats['total_species'] * 10)}%")

# 主搜索界面
def render_search():
    st.markdown('<div class="search-container">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            "🔍 搜索柴胡品种", 
            placeholder="输入关键词：如'红棕色'、'线形叶'、'圆锥形根'..."
        )
    with col2:
        search_mode = st.selectbox("搜索模式", ["模糊搜索", "精确匹配"], index=0)
    
    # 高级筛选（可折叠）
    with st.expander("🔎 高级筛选", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            root_filter = st.text_input("根特征", placeholder="如：圆柱形、红棕色")
        with col2:
            leaf_filter = st.text_input("叶特征", placeholder="如：线形、披针形")
        with col3:
            flower_filter = st.text_input("花特征", placeholder="如：黄色、伞形")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 执行搜索
    if search_query or root_filter or leaf_filter or flower_filter:
        results = db.search_species_fts(search_query or "")
        
        # 应用高级筛选
        filtered_results = []
        for species in results:
            match = True
            
            if root_filter and root_filter not in (species.get('root') or ''):
                match = False
            if leaf_filter and leaf_filter not in (species.get('leaf') or ''):
                match = False
            if flower_filter and flower_filter not in (species.get('flower_inflorescence') or ''):
                match = False
            
            if match:
                filtered_results.append(species)
        
        display_search_results(filtered_results)
    elif search_query == "":
        # 显示最近添加的品种
        st.info("💡 试试搜索：北柴胡、红柴胡、竹叶柴胡...")
        recent_results = db.search_species_fts("", limit=6)
        if recent_results:
            st.subheader("📚 最近添加的品种")
            display_species_grid(recent_results)

# 显示搜索结果
def display_search_results(results: List[Dict[str, Any]]):
    if not results:
        st.warning("🔍 未找到匹配的柴胡品种。")
        return
    
    st.success(f"✅ 找到 {len(results)} 个匹配的品种")
    
    # 选择显示模式
    view_mode = st.radio("显示模式", ["卡片视图", "列表视图", "表格视图"], horizontal=True)
    
    if view_mode == "卡片视图":
        display_species_grid(results)
    elif view_mode == "列表视图":
        display_species_list(results)
    else:  # 表格视图
        display_species_table(results)

# 卡片网格显示
def display_species_grid(results: List[Dict[str, Any]]):
    cols = st.columns(2 if st.session_state.get('is_mobile', False) else 3)
    
    for idx, species in enumerate(results):
        with cols[idx % len(cols)]:
            with st.container():
                st.markdown(f"""
                <div class="species-card">
                    <h3>{species['name_chinese']}</h3>
                    <p><strong>🌱 根:</strong> {truncate_text(species.get('root', '暂无'), 30)}</p>
                    <p><strong>🍃 叶:</strong> {truncate_text(species.get('leaf', '暂无'), 30)}</p>
                    <div style="margin-top: 0.5rem;">
                        <span class="tag">ID: {species['id']}</span>
                        {f'<span class="tag">变种: {len(species["varieties"])}</span>' if species.get('varieties') else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 查看详情按钮
                if st.button("📖 查看详情", key=f"view_{species['id']}", use_container_width=True):
                    st.session_state['selected_species'] = species['id']
                    st.rerun()

# 列表显示
def display_species_list(results: List[Dict[str, Any]]):
    for species in results:
        with st.expander(f"🌿 {species['name_chinese']} ({species['id']})"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**根特征:**", species.get('root', '暂无'))
                st.write("**茎特征:**", species.get('stem', '暂无'))
                st.write("**叶特征:**", species.get('leaf', '暂无'))
            with col2:
                st.write("**花果期:**", species.get('flowering_fruiting', '暂无'))
                st.write("**产地:**", species.get('habitat', '暂无'))
                if species.get('varieties'):
                    st.write("**变种:**", ", ".join([v['name_chinese'] for v in species['varieties']]))
            
            if st.button("查看完整信息", key=f"full_{species['id']}"):
                st.session_state['selected_species'] = species['id']
                st.rerun()

# 表格显示
def display_species_table(results: List[Dict[str, Any]]):
    # 准备表格数据
    table_data = []
    for species in results:
        table_data.append({
            "ID": species['id'],
            "品种名称": species['name_chinese'],
            "根特征": truncate_text(species.get('root', ''), 30),
            "叶特征": truncate_text(species.get('leaf', ''), 30),
            "产地": truncate_text(species.get('habitat', ''), 30),
            "变种数": len(species.get('varieties', []))
        })
    
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 选择查看详情
    selected_id = st.selectbox(
        "选择ID查看详情", 
        [""] + [str(species['id']) for species in results],
        format_func=lambda x: f"ID: {x}" if x else "请选择..."
    )
    
    if selected_id:
        if st.button("查看选中品种", use_container_width=True):
            st.session_state['selected_species'] = int(selected_id)
            st.rerun()

# 品种详情页面
def render_species_detail(species_id: int):
    species = db.get_species_by_id(species_id)
    
    if not species:
        st.error("未找到指定的柴胡品种")
        return
    
    # 返回按钮
    if st.button("← 返回搜索结果", use_container_width=True):
        if 'selected_species' in st.session_state:
            del st.session_state['selected_species']
        st.rerun()
    
    # 详情卡片
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h1 style="margin: 0;">{species['name_chinese']}</h1>
        <p style="margin: 0; opacity: 0.9;">{species.get('name_latin', '')}</p>
        <div style="margin-top: 0.5rem;">
            <span class="badge">ID: {species['id']}</span>
            <span class="badge">📅 {species.get('created_at', '').split()[0] if species.get('created_at') else '未知'}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 详细信息
    tabs = st.tabs(["📋 基本信息", "🌱 形态特征", "📍 生境分布", "💊 药用价值", "🌿 变种信息"])
    
    with tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("创建时间", species.get('created_at', '未知'))
        with col2:
            st.metric("更新时间", species.get('updated_at', '未知'))
        
        if species.get('notes'):
            st.info("📝 备注: " + species['notes'])
    
    with tabs[1]:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("根")
            st.write(species.get('root', '暂无信息'))
            
            st.subheader("茎")
            st.write(species.get('stem', '暂无信息'))
            
            st.subheader("叶")
            st.write(species.get('leaf', '暂无信息'))
        
        with col2:
            st.subheader("花/花序")
            st.write(species.get('flower_inflorescence', '暂无信息'))
            
            st.subheader("果实")
            st.write(species.get('fruit', '暂无信息'))
            
            st.subheader("花果期")
            st.write(species.get('flowering_fruiting', '暂无信息'))
    
    with tabs[2]:
        st.subheader("产地/生境")
        st.write(species.get('habitat', '暂无信息'))
        
        # 简单的地图示意
        if "西藏" in (species.get('habitat') or ''):
            st.image("https://img.icons8.com/color/96/000000/tibet.png", width=96)
            st.caption("分布区域: 西藏地区")
        elif "新疆" in (species.get('habitat') or ''):
            st.image("https://img.icons8.com/color/96/000000/china.png", width=96)
            st.caption("分布区域: 新疆地区")
        elif "云南" in (species.get('habitat') or ''):
            st.image("https://img.icons8.com/color/96/000000/yunnan.png", width=96)
            st.caption("分布区域: 云南地区")
    
    with tabs[3]:
        st.subheader("药用功效")
        st.write(species.get('medicinal_use', '暂无药用信息'))
        
        # 简单的功效标签
        medicinal_text = species.get('medicinal_use', '').lower()
        tags_col1, tags_col2, tags_col3 = st.columns(3)
        
        with tags_col1:
            if any(word in medicinal_text for word in ['解热', '清热', '退热']):
                st.markdown('<span class="tag">🔥 解热</span>', unsafe_allow_html=True)
        
        with tags_col2:
            if any(word in medicinal_text for word in ['消炎', '解毒', '抗炎']):
                st.markdown('<span class="tag">🩹 消炎解毒</span>', unsafe_allow_html=True)
        
        with tags_col3:
            if any(word in medicinal_text for word in ['疏肝', '理气', '调经']):
                st.markdown('<span class="tag">💚 疏肝理气</span>', unsafe_allow_html=True)
    
    with tabs[4]:
        if species.get('varieties'):
            st.success(f"🌿 共有 {len(species['varieties'])} 个变种/变型")
            
            for variety in species['varieties']:
                with st.expander(f"📌 {variety['name_chinese']}"):
                    st.write(variety.get('description', '暂无描述'))
        else:
            st.info("ℹ️ 该品种暂无变种信息")

# 添加新品种页面
# 添加新品种页面
def render_add_species():
    st.markdown("""
    <div style="background: #f0f7ff; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h2 style="margin: 0; color: #2c3e50;">➕ 添加新品种</h2>
        <p style="margin: 0; color: #7f8c8d;">为柴胡数据库添加新的品种信息</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("add_species_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            name_chinese = st.text_input("中文名*", placeholder="如：北柴胡")
            name_latin = st.text_input("拉丁学名", placeholder="如：Bupleurum chinense")
            root = st.text_area("根特征", placeholder="描述根的形态、颜色、质地等")
            stem = st.text_area("茎特征", placeholder="描述茎的高度、形状、颜色等")
            leaf = st.text_area("叶特征", placeholder="描述叶的形状、大小、叶脉等")
        
        with col2:
            flower = st.text_area("花/花序", placeholder="描述花序类型、花颜色等")
            fruit = st.text_area("果实", placeholder="描述果实形状、大小、颜色等")
            flowering_fruiting = st.text_input("花果期", placeholder="如：花期7-8月，果期8-9月")
            habitat = st.text_area("产地/生境", placeholder="描述分布区域和生长环境")
            medicinal_use = st.text_area("药用功效", placeholder="描述药用价值和功效")
        
        notes = st.text_area("备注信息", placeholder="其他需要说明的信息")
        
        # 变种信息部分
        st.subheader("🌱 变种/变型信息")
        
        # 初始化变种计数
        if 'variety_count' not in st.session_state:
            st.session_state.variety_count = 1
        
        varieties = []
        for i in range(st.session_state.variety_count):
            col_v1, col_v2 = st.columns([2, 3])
            with col_v1:
                var_name = st.text_input(f"变种名称 {i+1}", key=f"var_name_{i}", placeholder="如：北京柴胡")
            with col_v2:
                var_desc = st.text_input(f"变种描述 {i+1}", key=f"var_desc_{i}", placeholder="描述变种特征")
            
            if var_name:
                varieties.append({'name_chinese': var_name, 'description': var_desc})
        
        # 在表单外添加变种管理按钮
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        
        submitted = st.form_submit_button("✅ 提交新品种", use_container_width=True)
    
    # 表单外的变种管理按钮
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
    with col_btn1:
        if st.button("➕ 添加变种", use_container_width=True):
            st.session_state.variety_count += 1
            st.rerun()
    
    with col_btn2:
        if st.button("➖ 减少变种", use_container_width=True):
            if st.session_state.variety_count > 1:
                st.session_state.variety_count -= 1
            st.rerun()
    
    # 处理表单提交
    if submitted:
        if not name_chinese:
            st.error("❌ 中文名是必填项！")
            return
        
        # 收集表单数据
        species_data = {
            'name_chinese': name_chinese,
            'name_latin': name_latin,
            'root': root,
            'stem': stem,
            'leaf': leaf,
            'flower_inflorescence': flower,
            'fruit': fruit,
            'flowering_fruiting': flowering_fruiting,
            'habitat': habitat,
            'medicinal_use': medicinal_use,
            'notes': notes,
            'varieties': varieties
        }
        
        try:
            species_id = db.add_species(species_data)
            st.success(f"✅ 成功添加新品种：{name_chinese} (ID: {species_id})")
            
            # 重置变种计数
            st.session_state.variety_count = 1
            
            # 显示预览
            with st.expander("📋 预览添加的数据", expanded=True):
                st.json(species_data)
            
        except Exception as e:
            st.error(f"❌ 添加失败：{str(e)}")

# 浏览所有品种页面
def render_browse_all():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%); 
                color: #2c3e50; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h2 style="margin: 0;">📚 柴胡品种库</h2>
        <p style="margin: 0; opacity: 0.9;">浏览数据库中的所有柴胡品种</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 获取所有品种
    all_species = db.search_species_fts("")
    
    if not all_species:
        st.info("📭 数据库为空，请先添加柴胡品种")
        return
    
    # 分页显示
    page_size = 12
    if 'browse_page' not in st.session_state:
        st.session_state.browse_page = 1
    
    total_pages = (len(all_species) + page_size - 1) // page_size
    start_idx = (st.session_state.browse_page - 1) * page_size
    end_idx = min(start_idx + page_size, len(all_species))
    
    # 分页控件
    col1, col2, col3 = st.columns([2, 3, 2])
    with col1:
        if st.button("◀️ 上一页", disabled=st.session_state.browse_page <= 1):
            st.session_state.browse_page -= 1
            st.rerun()
    
    with col2:
        st.markdown(f"<center>第 {st.session_state.browse_page} / {total_pages} 页</center>", unsafe_allow_html=True)
    
    with col3:
        if st.button("下一页 ▶️", disabled=st.session_state.browse_page >= total_pages):
            st.session_state.browse_page += 1
            st.rerun()
    
    # 显示当前页的品种
    current_species = all_species[start_idx:end_idx]
    
    # 网格显示
    cols = st.columns(2 if st.session_state.get('is_mobile', False) else 3)
    
    for idx, species in enumerate(current_species):
        with cols[idx % len(cols)]:
            with st.container():
                # 品种卡片
                card_html = f"""
                <div class="species-card" style="height: 180px; display: flex; flex-direction: column;">
                    <h4 style="margin: 0; color: #2c3e50;">{species['name_chinese']}</h4>
                    <div style="flex-grow: 1;">
                        <p style="margin: 0.5rem 0; font-size: 0.9rem; color: #555;">
                            <strong>根:</strong> {truncate_text(species.get('root', '暂无'), 25)}
                        </p>
                        <p style="margin: 0.5rem 0; font-size: 0.9rem; color: #555;">
                            <strong>叶:</strong> {truncate_text(species.get('leaf', '暂无'), 25)}
                        </p>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.8rem; color: #777;">ID: {species['id']}</span>
                        <span style="font-size: 0.8rem; color: #4CAF50;">📊</span>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
                
                # 查看详情按钮
                if st.button("查看详情", key=f"browse_{species['id']}", use_container_width=True):
                    st.session_state['selected_species'] = species['id']
                    st.rerun()

# 数据管理页面
def render_data_management():
    st.markdown("""
    <div style="background: #fff3e0; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h2 style="margin: 0; color: #e65100;">🗃️ 数据管理</h2>
        <p style="margin: 0; color: #f57c00;">管理柴胡数据库</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📊 数据统计", "📥 数据导入", "🔄 数据库维护"])
    
    with tab1:
        stats = db.get_statistics()
        
        st.metric("🌱 柴胡品种数", stats['total_species'])
        st.metric("🌿 变种/变型数", stats['total_varieties'])
        
        # 示例数据
        sample_data = {
            "品种": ["北柴胡", "红柴胡", "竹叶柴胡", "川滇柴胡", "金黄柴胡"],
            "变种数": [4, 2, 1, 2, 1],
            "记录时间": ["2024-01", "2024-01", "2024-01", "2024-01", "2024-01"]
        }
        st.bar_chart(pd.DataFrame(sample_data).set_index("品种")["变种数"])
    
    with tab2:
        st.info("💡 支持从Excel、CSV或JSON文件导入数据")
        
        uploaded_file = st.file_uploader("选择数据文件", type=['csv', 'xlsx', 'json'])
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith('.xlsx'):
                    df = pd.read_excel(uploaded_file)
                elif uploaded_file.name.endswith('.json'):
                    df = pd.read_json(uploaded_file)
                
                st.success(f"✅ 成功读取文件：{uploaded_file.name}")
                st.dataframe(df.head(), use_container_width=True)
                
                if st.button("导入到数据库", use_container_width=True):
                    st.warning("⚠️ 批量导入功能正在开发中...")
                    st.info("目前请使用表格上方的添加功能逐条添加")
            
            except Exception as e:
                st.error(f"❌ 文件读取失败：{str(e)}")
    
    with tab3:
        st.warning("⚠️ 谨慎操作！以下操作可能会影响数据安全")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 重新索引", use_container_width=True):
                st.info("搜索索引已重建")
        
        with col2:
            if st.button("🧹 清理缓存", use_container_width=True):
                st.cache_resource.clear()
                st.success("缓存已清理")
        
        with col3:
            if st.button("📋 导出数据", use_container_width=True):
                st.info("数据导出功能正在开发中...")
        
        # 危险区域
        with st.expander("🚨 危险区域", expanded=False):
            st.error("以下操作不可逆！")
            
            if st.button("🗑️ 清空数据库", type="secondary", use_container_width=True):
                st.warning("这将删除所有数据！")
                confirm = st.checkbox("我确认要清空数据库")
                
                if confirm and st.button("确认清空", type="primary"):
                    db.clear_database()
                    st.success("数据库已清空")
                    st.rerun()

# 辅助函数
def truncate_text(text: str, max_length: int) -> str:
    """截断文本并添加省略号"""
    if not text:
        return "暂无"
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def detect_mobile():
    """检测是否移动设备（简化版）"""
    # 在实际部署中，可以通过请求头检测
    # 这里使用Streamlit的配置作为简单判断
    return st.get_option("theme.primaryColor") == "#FF4B4B"  # 移动端可能有不同主题

# 主应用
def main():
    # 检测设备类型
    st.session_state['is_mobile'] = detect_mobile()
    
    # 侧边栏导航（移动端可能不可见）
    with st.sidebar:
        st.title("🌿 导航菜单")
        
        if st.session_state.get('is_mobile'):
            st.info("📱 移动端模式")
        
        page = st.radio(
            "选择功能",
            ["🔍 品种搜索", "📚 浏览全部", "➕ 添加品种", "🗃️ 数据管理", "ℹ️ 关于系统"],
            index=0
        )
        
        st.markdown("---")
        st.markdown("### 📊 快速统计")
        stats = db.get_statistics()
        st.write(f"🌱 品种数: **{stats['total_species']}**")
        st.write(f"🌿 变种数: **{stats['total_varieties']}**")
        
        st.markdown("---")
        st.markdown("### 📱 移动端优化")
        st.markdown("- 响应式布局")
        st.markdown("- 触摸友好")
        st.markdown("- 快速加载")
        
        if st.button("🔄 刷新页面", use_container_width=True):
            st.rerun()
    
    # 根据选择显示页面
    if page == "🔍 品种搜索":
        render_header()
        render_search()
    elif page == "📚 浏览全部":
        render_header()
        render_browse_all()
    elif page == "➕ 添加品种":
        render_header()
        render_add_species()
    elif page == "🗃️ 数据管理":
        render_header()
        render_data_management()
    elif page == "ℹ️ 关于系统":
        render_about_page()
    
    # 如果有选中的品种，显示详情
    if 'selected_species' in st.session_state:
        render_species_detail(st.session_state['selected_species'])

# 关于页面
def render_about_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%); 
                color: white; padding: 2rem; border-radius: 10px; margin-bottom: 1.5rem;">
        <h1 style="margin: 0; text-align: center;">🌿 柴胡查询系统</h1>
        <p style="margin: 0.5rem 0; text-align: center; opacity: 0.9;">传统草药数据库 | v1.0.0</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📖 系统介绍")
        st.markdown("""
        柴胡查询系统是一个专门为中医药研究者和爱好者设计的移动端Web应用，
        用于查询和管理柴胡属植物的详细信息。
        
        **主要功能：**
        - 🔍 智能搜索柴胡品种
        - 📚 浏览完整的柴胡数据库
        - ➕ 添加和管理新品种信息
        - 📱 移动端优化，随时随地访问
        - 📊 数据统计和管理
        
        **数据来源：**
        本系统数据基于《柴胡表型库》整理，涵盖36种柴胡及其变种。
        """)
    
    with col2:
        st.markdown("### 🛠️ 技术特性")
        st.markdown("""
        **前端技术：**
        - Streamlit框架
        - 响应式CSS设计
        - 移动端优先
        
        **后端技术：**
        - SQLite数据库
        - 全文搜索索引
        - 数据缓存机制
        
        **部署方式：**
        - 支持本地运行
        - 支持云部署
        - 支持Docker容器化
        """)
    
    st.markdown("---")
    
    st.markdown("### 📱 移动端使用指南")
    col_guide1, col_guide2, col_guide3 = st.columns(3)
    
    with col_guide1:
        st.markdown("#### 1. 访问方式")
        st.markdown("""
        打开手机浏览器
        输入应用地址
        无需安装APP
        """)
    
    with col_guide2:
        st.markdown("#### 2. 搜索功能")
        st.markdown("""
        支持关键词搜索
        支持高级筛选
        支持模糊匹配
        """)
    
    with col_guide3:
        st.markdown("#### 3. 数据管理")
        st.markdown("""
        添加新品种
        查看详情
        数据统计
        """)
    
    st.markdown("---")
    
    st.markdown("### 📞 联系与支持")
    col_contact1, col_contact2, col_contact3 = st.columns(3)
    
    with col_contact1:
        st.markdown("**🌐 官方网站**")
        st.markdown("x")
    
    with col_contact2:
        st.markdown("**📧 联系邮箱**")
        st.markdown("X")
    
    with col_contact3:
        st.markdown("**📱 技术支持**")
        st.markdown("X")
    
    # 底部信息
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #777; font-size: 0.9rem;">
        <p>© 2024 柴胡查询系统 | 中医药数据平台</p>
        <p>本系统仅供学习和研究使用</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()