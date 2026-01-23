# 在 BupleurumDatabase 类中添加 import_from_csv 方法
import streamlit as st
import sqlite3
import re
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
import io
import csv

# 设置页面配置
st.set_page_config(
    page_title="柴胡查询系统",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 自定义CSS样式
def load_custom_css():
    st.markdown("""
    <style>
    .main { padding: 1rem; }
    
    @media (max-width: 768px) {
        .block-container { padding: 1rem 0.5rem; }
        .stButton > button { width: 100%; margin: 0.25rem 0; }
        .stSelectbox, .stTextInput, .stTextArea { width: 100%; }
    }
    
    .species-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 5px solid #4CAF50;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    .tag {
        display: inline-block;
        background: #4CAF50;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 15px;
        font-size: 0.8rem;
        margin: 0.2rem;
    }
    
    .search-container {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    
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
    
    .badge {
        display: inline-block;
        background: #FF9800;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.7rem;
        margin-left: 0.5rem;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
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
    """柴胡数据库管理类"""
    
    def __init__(self, db_path='bupleurum.db'):
        self.db_path = db_path
        self.conn = None
        self.initialize_database()
    
    def connect(self):
        """连接到数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        # 启用外键约束
        self.conn.execute("PRAGMA foreign_keys = ON")
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
            
            # 创建全文搜索索引 - 修复：添加name_latin列
            cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS species_fts USING fts5(
                name_chinese, name_latin, root, stem, leaf, flower_inflorescence, 
                fruit, flowering_fruiting, habitat, medicinal_use, notes,
                content='bupleurum_species',
                content_rowid='id'
            )
            ''')
            
            conn.commit()
    
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
            sql = f"INSERT OR REPLACE INTO bupleurum_species ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(sql, values)
            species_id = cursor.lastrowid
            
            # 如果有变种，先删除旧的变种
            cursor.execute("DELETE FROM varieties WHERE species_id = ?", (species_id,))
            
            # 插入新变种
            for variety in varieties:
                if variety.get('name_chinese'):  # 确保变种名称不为空
                    cursor.execute(
                        "INSERT INTO varieties (species_id, name_chinese, description) VALUES (?, ?, ?)",
                        (species_id, variety.get('name_chinese', ''), variety.get('description', ''))
                    )
            
            # 更新全文搜索索引 - 修复：使用正确的列名
            fts_columns = [
                'name_chinese', 'name_latin', 'root', 'stem', 'leaf',
                'flower_inflorescence', 'fruit', 'flowering_fruiting',
                'habitat', 'medicinal_use', 'notes'
            ]
            
            # 获取每个列的值，如果species_data中没有该列则使用空字符串
            fts_values = []
            for col in fts_columns:
                if col in species_data:
                    fts_values.append(species_data[col])
                else:
                    fts_values.append('')
            
            # 删除旧的FTS记录
            cursor.execute("DELETE FROM species_fts WHERE rowid = ?", (species_id,))
            
            # 插入新的FTS记录
            cursor.execute(f"""
            INSERT INTO species_fts(rowid, {', '.join(fts_columns)})
            VALUES (?, {', '.join(['?'] * len(fts_columns))})
            """, [species_id] + fts_values)
            
            conn.commit()
            return species_id
    
    def import_from_csv(self, df: pd.DataFrame) -> Dict[str, Any]:
        """从DataFrame批量导入数据"""
        results = {
            'total': len(df),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for idx, row in df.iterrows():
            try:
                # 处理变种信息
                varieties = []
                if 'varieties' in row and pd.notna(row['varieties']):
                    var_list = str(row['varieties']).split(';')
                    for var_name in var_list:
                        if var_name.strip():
                            varieties.append({
                                'name_chinese': var_name.strip(),
                                'description': ''
                            })
                
                # 准备物种数据 - 排除id列，因为数据库会自动生成
                species_data = {}
                
                # 定义需要处理的字段
                fields = [
                    'name_chinese', 'name_latin', 'root', 'stem', 'leaf', 
                    'flower_inflorescence', 'fruit', 'flowering_fruiting', 
                    'habitat', 'medicinal_use', 'notes'
                ]
                
                for field in fields:
                    if field in row and pd.notna(row[field]):
                        species_data[field] = str(row[field]).strip()
                    else:
                        species_data[field] = ''
                
                # 确保中文名不为空
                if not species_data['name_chinese']:
                    raise ValueError("中文名不能为空")
                
                # 添加变种信息
                species_data['varieties'] = varieties
                
                # 添加物种
                self.add_species(species_data)
                results['success'] += 1
                
            except Exception as e:
                results['failed'] += 1
                species_name = str(row.get('name_chinese', f"行{idx+2}")).strip()  # idx+2 因为从0开始，且CSV有标题行
                results['errors'].append(f"{species_name}: {str(e)}")
        
        return results
    
    def search_species_fts(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """使用全文搜索查询柴胡品种"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            if not query or query.strip() == "":
                cursor.execute("""
                SELECT bs.* 
                FROM bupleurum_species bs
                ORDER BY bs.name_chinese
                LIMIT ?
                """, (limit,))
            else:
                # 使用LIKE进行简单搜索，避免FTS5问题
                search_pattern = f"%{query}%"
                cursor.execute("""
                SELECT bs.* 
                FROM bupleurum_species bs
                WHERE bs.name_chinese LIKE ? 
                   OR bs.name_latin LIKE ? 
                   OR bs.root LIKE ? 
                   OR bs.stem LIKE ? 
                   OR bs.leaf LIKE ? 
                   OR bs.flower_inflorescence LIKE ? 
                   OR bs.fruit LIKE ? 
                   OR bs.flowering_fruiting LIKE ? 
                   OR bs.habitat LIKE ? 
                   OR bs.medicinal_use LIKE ? 
                   OR bs.notes LIKE ?
                ORDER BY bs.name_chinese
                LIMIT ?
                """, (search_pattern, search_pattern, search_pattern, search_pattern, 
                      search_pattern, search_pattern, search_pattern, search_pattern,
                      search_pattern, search_pattern, search_pattern, limit))
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                result['varieties'] = self.get_varieties(result['id'])
                results.append(result)
            
            return results
    
    def get_species_by_id(self, species_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取柴胡品种"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # 获取主品种信息
            cursor.execute("SELECT * FROM bupleurum_species WHERE id = ?", (species_id,))
            row = cursor.fetchone()
            
            if row:
                result = dict(row)
                # 获取变种信息
                result['varieties'] = self.get_varieties(species_id)
                return result
            
            return None
    
    def get_varieties(self, species_id: int) -> List[Dict[str, str]]:
        """获取品种的变种信息"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name_chinese, description FROM varieties WHERE species_id = ?", (species_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_species_names(self) -> List[str]:
        """获取所有柴胡品种名称"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name_chinese FROM bupleurum_species ORDER BY name_chinese")
            return [row[0] for row in cursor.fetchall()]
    
    def clear_database(self):
        """清空数据库"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM varieties")
            cursor.execute("DELETE FROM bupleurum_species")
            cursor.execute("DELETE FROM species_fts")
            conn.commit()
    
    def export_to_csv(self) -> str:
        """导出数据为CSV格式"""
        with self.connect() as conn:
            # 获取所有物种数据
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bupleurum_species ORDER BY name_chinese")
            species_data = [dict(row) for row in cursor.fetchall()]
            
            # 为每个物种获取变种
            for species in species_data:
                varieties = self.get_varieties(species['id'])
                if varieties:
                    species['varieties'] = ';'.join([v['name_chinese'] for v in varieties if v.get('name_chinese')])
                else:
                    species['varieties'] = ''
            
            # 转换为DataFrame
            df = pd.DataFrame(species_data)
            
            # 删除不需要的列
            columns_to_drop = ['id', 'created_at', 'updated_at']
            for col in columns_to_drop:
                if col in df.columns:
                    df = df.drop(columns=[col])
            
            return df.to_csv(index=False, encoding='utf-8-sig')

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
        st.metric("📊 数据库状态", "正常" if stats['total_species'] > 0 else "空")

# 批量导入页面
def render_bulk_import():
    st.markdown("""
    <div style="background: #f0f7ff; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h2 style="margin: 0; color: #2c3e50;">📥 批量导入数据</h2>
        <p style="margin: 0; color: #7f8c8d;">从CSV文件批量导入柴胡品种数据</p>
    </div>
    """, unsafe_allow_html=True)
    
    # CSV文件模板
    st.markdown("### 📋 CSV文件格式说明")
    st.markdown("""
    请使用以下格式的CSV文件进行导入：
    - 文件编码：UTF-8
    - 字段说明：
      1. **name_chinese** - 中文名（必填）
      2. **name_latin** - 拉丁学名（可选）
      3. **root** - 根特征（可选）
      4. **stem** - 茎特征（可选）
      5. **leaf** - 叶特征（可选）
      6. **flower_inflorescence** - 花/花序特征（可选）
      7. **fruit** - 果实特征（可选）
      8. **flowering_fruiting** - 花果期（可选）
      9. **habitat** - 产地/生境（可选）
      10. **medicinal_use** - 药用功效（可选）
      11. **notes** - 备注信息（可选）
      12. **varieties** - 变种信息（多个变种用分号分隔，可选）
    """)
    
    # 下载模板按钮
    template_data = {
        'name_chinese': ['北柴胡', '红柴胡'],
        'name_latin': ['Bupleurum chinense', 'Bupleurum scorzonerifolium'],
        'root': ['主根较粗大，棕褐色，质坚硬', '主根发达，圆锥形，深红棕色'],
        'stem': ['茎单一或数茎，高50-85厘米', '茎单一或2-3，高30-60厘米'],
        'leaf': ['基生叶倒披针形或狭椭圆形', '叶细线形，基生叶下部略收缩成叶柄'],
        'flower_inflorescence': ['复伞形花序很多，伞辐3-8', '伞形花序自叶腋间抽出，伞辐4-6'],
        'fruit': ['果广椭圆形，棕色，长约3毫米', '果广椭圆形，深褐色，长2.5毫米'],
        'flowering_fruiting': ['花期9月，果期10月', '花期7-8月，果期8-9月'],
        'habitat': ['我国东北、华北、西北、华东和华中各地', '广布于我国多个省区'],
        'medicinal_use': ['中药材上称为北柴胡', '根入药，称红柴胡'],
        'notes': ['分布广泛', '与锥叶柴胡极近似'],
        'varieties': ['北京柴胡;烟台柴胡;多伞北柴胡', '长伞红柴胡;少花红柴胡']
    }
    
    template_df = pd.DataFrame(template_data)
    csv_template = template_df.to_csv(index=False, encoding='utf-8-sig')
    
    st.download_button(
        label="📥 下载导入模板",
        data=csv_template,
        file_name="柴胡导入模板.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    st.markdown("---")
    
    # 文件上传区域
    st.markdown("### 📤 上传CSV文件")
    uploaded_file = st.file_uploader("选择CSV文件", type=['csv'])
    
    if uploaded_file is not None:
        try:
            # 尝试以不同编码读取CSV文件
            try:
                # 首先尝试utf-8-sig编码（处理BOM）
                df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            except:
                # 如果失败，尝试gbk编码
                uploaded_file.seek(0)  # 重置文件指针
                df = pd.read_csv(uploaded_file, encoding='gbk')
            
            # 清理列名：移除BOM和空白字符
            df.columns = [col.strip().replace('\ufeff', '') for col in df.columns]
            
            # 显示预览
            st.markdown("### 👀 数据预览")
            st.dataframe(df.head(), use_container_width=True)
            
            # 显示实际读取到的列名
            st.markdown("#### 📝 检测到的列名")
            st.write(f"列名列表: {list(df.columns)}")
            
            # 检查必要字段
            required_fields = ['name_chinese']
            missing_fields = [field for field in required_fields if field not in df.columns]
            
            if missing_fields:
                st.error(f"❌ CSV文件缺少必要字段: {', '.join(missing_fields)}")
                st.info(f"检测到的字段: {', '.join(df.columns)}")
            else:
                st.success(f"✅ 成功读取文件，共发现 {len(df)} 条记录")
                
                # 显示字段统计
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("总记录数", len(df))
                with col2:
                    filled_names = df['name_chinese'].dropna().count()
                    st.metric("有效中文名", filled_names)
                with col3:
                    if 'varieties' in df.columns:
                        variety_count = df['varieties'].dropna().count()
                        st.metric("包含变种", variety_count)
                    else:
                        st.metric("包含变种", 0)
                
                # 导入确认
                if st.button("🚀 开始导入数据", type="primary", use_container_width=True):
                    with st.spinner("正在导入数据..."):
                        result = db.import_from_csv(df)
                    
                    # 显示导入结果
                    st.markdown("### 📊 导入结果")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("总记录数", result['total'])
                    with col2:
                        st.metric("导入成功", result['success'])
                    with col3:
                        st.metric("导入失败", result['failed'])
                    
                    if result['success'] > 0:
                        st.success(f"✅ 成功导入 {result['success']} 条记录")
                    
                    if result['failed'] > 0:
                        st.error(f"❌ 有 {result['failed']} 条记录导入失败")
                        with st.expander("查看错误详情"):
                            for error in result['errors']:
                                st.write(f"- {error}")
                    
                    # 更新统计信息
                    st.rerun()
        
        except Exception as e:
            st.error(f"❌ 文件读取失败: {str(e)}")
            import traceback
            st.error(f"详细错误信息: {traceback.format_exc()}")
    
    # 数据导出功能
    st.markdown("---")
    st.markdown("### 📤 数据导出")
    
    if st.button("📥 导出当前数据为CSV", use_container_width=True):
        try:
            csv_data = db.export_to_csv()
            st.download_button(
                label="下载CSV文件",
                data=csv_data,
                file_name="柴胡数据库导出.csv",
                mime="text/csv",
                use_container_width=True
            )
            st.success("✅ 数据导出完成，请点击上方按钮下载")
        except Exception as e:
            st.error(f"❌ 导出失败: {str(e)}")

# 主搜索界面
def render_search():
    st.markdown('<div class="search-container">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            "🔍 搜索柴胡品种", 
            placeholder="输入关键词：如'红棕色'、'线形叶'、'圆锥形根'..."
        )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 执行搜索
    if search_query and search_query.strip() != "":
        results = db.search_species_fts(search_query)
        display_search_results(results)
    else:
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
    
    view_mode = st.radio("显示模式", ["卡片视图", "列表视图", "表格视图"], horizontal=True)
    
    if view_mode == "卡片视图":
        display_species_grid(results)
    elif view_mode == "列表视图":
        display_species_list(results)
    else:
        display_species_table(results)

# 卡片网格显示
def display_species_grid(results: List[Dict[str, Any]]):
    cols = st.columns(2)
    
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
            
            if st.button("查看完整信息", key=f"full_{species['id']}", use_container_width=True):
                st.session_state['selected_species'] = species['id']
                st.rerun()

# 表格显示
def display_species_table(results: List[Dict[str, Any]]):
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
    with st.spinner("加载中..."):
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
    
    tabs = st.tabs(["📋 基本信息", "🌱 形态特征", "📍 生境分布", "💊 药用价值", "🌿 变种信息"])
    
    with tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("创建时间", species.get('created_at', '未知').split()[0])
        with col2:
            st.metric("更新时间", species.get('updated_at', '未知').split()[0])
        
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
    
    with tabs[3]:
        st.subheader("药用功效")
        st.write(species.get('medicinal_use', '暂无药用信息'))
    
    with tabs[4]:
        if species.get('varieties'):
            st.success(f"🌿 共有 {len(species['varieties'])} 个变种/变型")
            for variety in species['varieties']:
                with st.expander(f"📌 {variety['name_chinese']}"):
                    st.write(variety.get('description', '暂无描述'))
        else:
            st.info("ℹ️ 该品种暂无变种信息")

# 添加新品种页面
def render_add_species():
    st.markdown("""
    <div style="background: #f0f7ff; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h2 style="margin: 0; color: #2c3e50;">➕ 添加新品种</h2>
        <p style="margin: 0; color: #7f8c8d;">为柴胡数据库添加新的品种信息</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 初始化变种计数
    if 'variety_count' not in st.session_state:
        st.session_state.variety_count = 1
    
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
        
        # 变种信息
        st.subheader("🌱 变种/变型信息")
        
        varieties = []
        for i in range(st.session_state.variety_count):
            col_v1, col_v2 = st.columns([2, 3])
            with col_v1:
                var_name = st.text_input(f"变种名称 {i+1}", key=f"var_name_{i}", placeholder="如：北京柴胡")
            with col_v2:
                var_desc = st.text_input(f"变种描述 {i+1}", key=f"var_desc_{i}", placeholder="描述变种特征")
            
            if var_name:
                varieties.append({'name_chinese': var_name, 'description': var_desc})
        
        submitted = st.form_submit_button("✅ 提交新品种", use_container_width=True)
        
        if submitted:
            if not name_chinese:
                st.error("❌ 中文名是必填项！")
                return
            
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
                
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ 添加失败：{str(e)}")
    
    # 变种管理按钮（在表单外）
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

# 数据管理页面
def render_data_management():
    st.markdown("""
    <div style="background: #fff3e0; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h2 style="margin: 0; color: #e65100;">🗃️ 数据管理</h2>
        <p style="margin: 0; color: #f57c00;">管理柴胡数据库</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 数据统计", "📥 批量导入", "🔄 数据库维护", "📤 数据导出"])
    
    with tab1:
        stats = db.get_statistics()
        
        st.metric("🌱 柴胡品种数", stats['total_species'])
        st.metric("🌿 变种/变型数", stats['total_varieties'])
        
        # 显示品种列表
        all_species = db.search_species_fts("", limit=100)
        if all_species:
            st.subheader("📋 品种列表")
            species_names = [s['name_chinese'] for s in all_species]
            st.write(", ".join(species_names))
    
    with tab2:
        render_bulk_import()
    
    with tab3:
        st.warning("⚠️ 谨慎操作！以下操作可能会影响数据安全")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 重建索引", use_container_width=True):
                try:
                    # 重建全文搜索索引
                    with db.connect() as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM species_fts")
                        cursor.execute("""
                        INSERT INTO species_fts(rowid, name_chinese, name_latin, root, stem, leaf, 
                                              flower_inflorescence, fruit, flowering_fruiting, 
                                              habitat, medicinal_use, notes)
                        SELECT id, name_chinese, name_latin, root, stem, leaf, 
                               flower_inflorescence, fruit, flowering_fruiting, 
                               habitat, medicinal_use, notes
                        FROM bupleurum_species
                        """)
                        conn.commit()
                    st.success("✅ 全文搜索索引已重建")
                except Exception as e:
                    st.error(f"❌ 重建索引失败：{str(e)}")
        
        with col2:
            if st.button("🧹 清理缓存", use_container_width=True):
                st.cache_resource.clear()
                st.success("✅ 缓存已清理")
        
        # 危险区域
        with st.expander("🚨 危险区域", expanded=False):
            st.error("以下操作不可逆！")
            
            if st.button("🗑️ 清空数据库", type="secondary", use_container_width=True):
                st.warning("这将删除所有数据！")
                confirm = st.checkbox("我确认要清空数据库")
                
                if confirm:
                    if st.button("确认清空", type="primary"):
                        db.clear_database()
                        st.success("✅ 数据库已清空")
                        st.rerun()
    
    with tab4:
        st.markdown("### 📤 导出数据")
        st.info("将当前数据库中的所有数据导出为CSV文件")
        
        if st.button("📥 导出数据为CSV", use_container_width=True):
            try:
                csv_data = db.export_to_csv()
                
                st.download_button(
                    label="下载CSV文件",
                    data=csv_data,
                    file_name=f"柴胡数据库_导出_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                st.success("✅ 数据导出完成，请点击上方按钮下载")
            except Exception as e:
                st.error(f"❌ 导出失败: {str(e)}")

# 辅助函数
def truncate_text(text: str, max_length: int) -> str:
    """截断文本并添加省略号"""
    if not text:
        return "暂无"
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

# 主应用
def main():
    # 侧边栏导航
    with st.sidebar:
        st.title("🌿 导航菜单")
        
        page = st.radio(
            "选择功能",
            ["🔍 品种搜索", "📚 浏览全部", "➕ 添加品种", "📥 批量导入", "🗃️ 数据管理", "ℹ️ 关于系统"],
            index=0
        )
        
        st.markdown("---")
        st.markdown("### 📊 快速统计")
        stats = db.get_statistics()
        st.write(f"🌱 品种数: **{stats['total_species']}**")
        st.write(f"🌿 变种数: **{stats['total_varieties']}**")
        
        st.markdown("---")
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
    elif page == "📥 批量导入":
        render_header()
        render_bulk_import()
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
        <p style="margin: 0.5rem 0; text-align: center; opacity: 0.9;">传统草药数据库 | v2.0.0</p>
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
        - 📥 批量导入/导出数据
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
        批量导入/导出
        数据统计
        """)

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
        if st.button("📥 前往批量导入页面"):
            st.session_state['page'] = "📥 批量导入"
            st.rerun()
        return
    
    # 显示统计
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🌱 品种总数", len(all_species))
    with col2:
        total_varieties = sum(len(s.get('varieties', [])) for s in all_species)
        st.metric("🌿 变种总数", total_varieties)
    with col3:
        st.metric("📅 最后更新", max([s.get('updated_at', '') for s in all_species if s.get('updated_at')])[:10] if all_species else "无")
    
    # 品种列表
    st.subheader("📋 品种列表")
    
    # 搜索筛选
    search_filter = st.text_input("🔍 筛选品种", placeholder="输入品种名称...")
    
    filtered_species = all_species
    if search_filter:
        filtered_species = [s for s in all_species if search_filter.lower() in s['name_chinese'].lower()]
    
    # 分页显示
    page_size = 12
    if 'browse_page' not in st.session_state:
        st.session_state.browse_page = 1
    
    total_pages = max(1, (len(filtered_species) + page_size - 1) // page_size)
    start_idx = (st.session_state.browse_page - 1) * page_size
    end_idx = min(start_idx + page_size, len(filtered_species))
    
    # 分页控件
    col1, col2, col3 = st.columns([2, 3, 2])
    with col1:
        if st.button("◀️ 上一页", disabled=st.session_state.browse_page <= 1, use_container_width=True):
            st.session_state.browse_page -= 1
            st.rerun()
    
    with col2:
        st.markdown(f"<center>第 {st.session_state.browse_page} / {total_pages} 页</center>", unsafe_allow_html=True)
    
    with col3:
        if st.button("下一页 ▶️", disabled=st.session_state.browse_page >= total_pages, use_container_width=True):
            st.session_state.browse_page += 1
            st.rerun()
    
    # 显示当前页的品种
    current_species = filtered_species[start_idx:end_idx]
    
    # 网格显示
    cols = st.columns(2)
    
    for idx, species in enumerate(current_species):
        with cols[idx % len(cols)]:
            with st.container():
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
                
                if st.button("查看详情", key=f"browse_{species['id']}", use_container_width=True):
                    st.session_state['selected_species'] = species['id']
                    st.rerun()

if __name__ == "__main__":
    main()
