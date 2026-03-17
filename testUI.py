# testUI_redesigned.py
import streamlit as st
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional
import io
import re

# 设置页面配置
st.set_page_config(
    page_title="柴胡形态特征数据库",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)
# 中文优先排序
def chinese_first_key(species):
    """排序键：纯中文/中文为主的名称返回0，含英文的返回1"""
    name = species.get('species_name', '')
    # 简单判断：如果名称包含任何ASCII字母（A-Z a-z），则认为含英文
    import re
    if re.search(r'[A-Za-z]', name):
        return 1
    else:
        return 0
        
# 自定义CSS样式
def load_custom_css():
    st.markdown("""
    <style>
    .main { padding: 1rem; }
    
    .species-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 5px solid #4CAF50;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    .feature-tag {
        display: inline-block;
        background: #4CAF50;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 15px;
        font-size: 0.8rem;
        margin: 0.2rem;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        text-align: center;
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
    
    .custom-title {
        background: linear-gradient(45deg, #4CAF50, #2E7D32);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    
    .feature-group {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border: 1px solid #e9ecef;
    }
    
    .data-table {
        font-size: 0.9rem;
    }
    
    .data-table th {
        background-color: #4CAF50;
        color: white;
        padding: 0.5rem;
    }
    
    .data-table td {
        padding: 0.5rem;
        border-bottom: 1px solid #ddd;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# 加载CSS
load_custom_css()

class BupleurumMorphologyDB:
    """柴胡形态特征数据库管理类"""
    
    def __init__(self, db_path='bupleurum_morphology.db'):
        self.db_path = db_path
        self.conn = None
        self.initialize_database()
    
    def connect(self):
        """连接到数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def initialize_database(self):
        """初始化数据库表 - 根据Excel结构设计"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # 创建主表（如果不存在）
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bupleurum_species (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial_number INTEGER,
                species_name TEXT NOT NULL,
                is_subspecies TEXT,                -- 是否亚种
                original_species TEXT,              -- 原种名称
                subspecies_no TEXT,                 -- 亚种编号
                growth_form TEXT,
                min_height_cm REAL,
                max_height_cm REAL,
                root_color TEXT,
                leaf_shape TEXT,
                leaf_position TEXT,                 -- 叶位置
                leaf_min_length_cm REAL,
                leaf_max_length_cm REAL,
                leaf_min_width_cm REAL,              -- 注意单位改为厘米
                leaf_max_width_cm REAL,
                leaf_color TEXT,
                min_vein_number INTEGER,
                max_vein_number INTEGER,
                leaf_unique_features TEXT,           -- 叶独特特征
                plant_features TEXT,                 -- 植株特征
                fruit_features TEXT,                  -- 果实特征
                min_inflorescence_diameter_cm REAL,
                max_inflorescence_diameter_cm REAL,
                bract_number TEXT,
                bract_shape TEXT,
                min_bract_length_cm REAL,             -- 单位改为厘米
                max_bract_length_cm REAL,
                ray_number TEXT,
                min_ray_length_cm REAL,
                max_ray_length_cm REAL,
                umbellet_diameter_min_cm REAL,        -- 拆分为最小/最大
                umbellet_diameter_max_cm REAL,
                bracteole_number TEXT,
                bracteole_shape TEXT,
                umbellet_number TEXT,
                petal_color TEXT,
                fruit_shape TEXT,
                fruit_color TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # 检查并添加 description 字段（如果不存在）
            cursor.execute("PRAGMA table_info(bupleurum_species)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'description' not in columns:
                cursor.execute("ALTER TABLE bupleurum_species ADD COLUMN description TEXT")
                print("字段 'description' 已添加到数据库表。")
            
            # 创建索引（保持不变）
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_species_name ON bupleurum_species(species_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_growth_form ON bupleurum_species(growth_form)')
            
            conn.commit()
            
      
    def import_from_excel_df(self, df: pd.DataFrame) -> Dict[str, Any]:
        st.write("上传文件的列名：", list(df.columns))
        results = {'total': len(df), 'success': 0, 'failed': 0, 'errors': [], 'duplicates': 0}
        existing_species = self.get_all_species_names()
        
        for idx, row in df.iterrows():
            try:
                species_name = str(row.get('物种名称', '')).strip()
                if not species_name or species_name == 'nan':
                    results['failed'] += 1
                    results['errors'].append(f"行{idx+1}: 物种名称为空")
                    continue
                if species_name in existing_species:
                    results['duplicates'] += 1
                    continue

                species_data = {
                    'serial_number': self._parse_integer(row.get('序号')),
                    'species_name': species_name,
                    'is_subspecies': str(row.get('是否亚种', '')).strip(),
                    'original_species': str(row.get('原种名称', '')).strip(),
                    'subspecies_no': str(row.get('亚种编号', '')).strip(),
                    'growth_form': str(row.get('株型', '')).strip(),
                    'min_height_cm': self._parse_numeric(row.get('最小株高')),
                    'max_height_cm': self._parse_numeric(row.get('最大株高')),
                    'root_color': str(row.get('根颜色', '')).strip(),
                    'leaf_shape': str(row.get('叶形', '')).strip(),
                    'leaf_position': str(row.get('叶位置', '')).strip(),
                    'leaf_min_length_cm': self._parse_numeric(row.get('叶最小长度_cm')),
                    'leaf_max_length_cm': self._parse_numeric(row.get('叶最大长度_cm')),
                    'leaf_min_width_cm': self._parse_numeric(row.get('叶最小宽度_cm')),
                    'leaf_max_width_cm': self._parse_numeric(row.get('叶最大宽度_cm')),
                    'leaf_color': str(row.get('叶颜色', '')).strip(),
                    'min_vein_number': self._parse_integer(row.get('最小叶脉数')),
                    'max_vein_number': self._parse_integer(row.get('最大叶脉数')),
                    'leaf_unique_features': str(row.get('叶独特特征', '')).strip(),
                    'plant_features': str(row.get('植株特征', '')).strip(),
                    'fruit_features': str(row.get('果实特征', '')).strip(),
                    'min_inflorescence_diameter_cm': self._parse_numeric(row.get('最小花序直径_cm')),
                    'max_inflorescence_diameter_cm': self._parse_numeric(row.get('最大花序直径_cm')),
                    'bract_number': str(row.get('总苞片数量', '')).strip(),
                    'bract_shape': str(row.get('总苞片形状', '')).strip(),
                    'min_bract_length_cm': self._parse_numeric(row.get('总苞片最小长度_cm')),
                    'max_bract_length_cm': self._parse_numeric(row.get('总苞片最大长度_cm')),
                    'ray_number': str(row.get('伞幅数量', '')).strip(),   # 注意是“幅”不是“辐”
                    'min_ray_length_cm': self._parse_numeric(row.get('最小伞幅长度_cm')),
                    'max_ray_length_cm': self._parse_numeric(row.get('最大伞幅长度_cm')),
                    'umbellet_diameter_min_cm': self._parse_numeric(row.get('小伞形花序直径_min_cm')),
                    'umbellet_diameter_max_cm': self._parse_numeric(row.get('小伞形花序直径_max_cm')),
                    'bracteole_number': str(row.get('小总苞片数量', '')).strip(),
                    'bracteole_shape': str(row.get('小总苞片形状', '')).strip(),
                    'umbellet_number': str(row.get('小伞形花序数量', '')).strip(),
                    'petal_color': str(row.get('花瓣颜色', '')).strip(),
                    'fruit_shape': str(row.get('果形状', '')).strip(),
                    'fruit_color': str(row.get('果颜色', '')).strip()
                }

                self._add_species(species_data)
                results['success'] += 1
                existing_species.add(species_name)

            except Exception as e:
                results['failed'] += 1
                species_name = str(row.get('物种名称', f"行{idx+1}")).strip()
                results['errors'].append(f"{species_name}: {str(e)}")

        return results
        
    def _parse_numeric(self, value: str) -> Optional[float]:
        """解析数值，处理范围、未明确等情况"""
        if not value or value.lower() in ['未明确', 'nan', 'na', 'NA','']:
            return None
        
        # 处理范围值如 "3-8"
        if '-' in value:
            parts = value.split('-')
            try:
                return float(parts[0].strip())
            except:
                return None
        
        # 处理单个数值
        try:
            return float(value.strip())
        except:
            return None
    
    def _parse_integer(self, value: str) -> Optional[int]:
        """解析整数值"""
        num = self._parse_numeric(value)
        return int(num) if num is not None else None
    
    def _add_species(self, species_data: Dict[str, Any]) -> int:
        """添加物种到数据库"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            columns = list(species_data.keys())
            placeholders = ['?'] * len(columns)
            values = list(species_data.values())
            
            sql = f"INSERT INTO bupleurum_species ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(sql, values)
            conn.commit()
            return cursor.lastrowid
    
    def get_all_species(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取所有物种"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM bupleurum_species ORDER BY species_name LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_species_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取物种"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bupleurum_species WHERE species_name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def search_species(self, query: str = "", filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """搜索物种，支持文本搜索和高级筛选"""
        with self.connect() as conn:
            cursor = conn.cursor()
    
            # 获取表的所有列名，用于验证
            cursor.execute("PRAGMA table_info(bupleurum_species)")
            columns_info = cursor.fetchall()
            valid_columns = {col[1] for col in columns_info}
    
            sql = "SELECT * FROM bupleurum_species WHERE 1=1"
            params = []
    
            # 文本搜索
            if query:
                sql += " AND (species_name LIKE ? OR leaf_shape LIKE ? OR fruit_shape LIKE ?)"
                search_term = f"%{query}%"
                params.extend([search_term, search_term, search_term])
    
            # 单值范围字段映射：前端键名 -> (最小列名, 最大列名)
            single_range_map = {
                'height': ('min_height_cm', 'max_height_cm'),
                'leaf_length': ('leaf_min_length_cm', 'leaf_max_length_cm'),
                'leaf_width': ('leaf_min_width_cm', 'leaf_max_width_cm'),
                'vein_number': ('min_vein_number', 'max_vein_number'),
                'inflorescence_diameter': ('min_inflorescence_diameter_cm', 'max_inflorescence_diameter_cm'),
                'ray_length': ('min_ray_length_cm', 'max_ray_length_cm'),
                'bract_length': ('min_bract_length_cm', 'max_bract_length_cm'),
                'umbellet_diameter': ('umbellet_diameter_min_cm', 'umbellet_diameter_max_cm'),
            }
    
            if filters:
                for key, value in filters.items():
                    if value is None or value == '':
                        continue
    
                    if key in single_range_map:
                        col_min, col_max = single_range_map[key]
                        if col_min in valid_columns and col_max in valid_columns:
                            # 处理 NULL 值：如果某一端缺失，则忽略该端限制
                            sql += f" AND ({col_min} <= ? OR {col_min} IS NULL) AND ({col_max} >= ? OR {col_max} IS NULL)"
                            params.extend([float(value), float(value)])
                    else:
                        # 文本字段模糊匹配
                        if key in valid_columns:
                            sql += f" AND {key} LIKE ?"
                            params.append(f"%{value}%")
                        else:
                            print(f"忽略未知的筛选字段: {key}")
    
            sql += " ORDER BY species_name"
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
                
    def import_descriptions_from_excel(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        从“柴胡表型库”DataFrame导入物种描述，更新到现有物种记录。
        期望的DataFrame结构：至少包含两列，第一列为物种名称，第二列为详细描述。
        如果存在第三列（英文描述），也会被合并。
        """
        results = {
            'total': len(df),
            'matched': 0,
            'updated': 0,
            'not_found': [],
            'errors': []
        }
        
        # 获取所有现有物种名称（用于快速匹配）
        existing_names = {name.lower().strip(): name for name in self.get_all_species_names()}
        
        for idx, row in df.iterrows():
            try:
                # 假设第一列是物种名称，第二列是中文描述，第四列是英文描述（根据您提供的表型库结构调整）
                name_cell = str(row.iloc[0]).strip()
                if pd.isna(name_cell) or name_cell == '':
                    continue
                    
                # 提取描述：第二列（中文） + 第四列（英文）如果有的话
                desc_cn = str(row.iloc[1]) if len(row) > 1 and not pd.isna(row.iloc[1]) else ''
                desc_en = str(row.iloc[3]) if len(row) > 3 and not pd.isna(row.iloc[3]) else ''
                
                # 合并描述，可以用分隔符分开
                full_description = desc_cn
                if desc_en:
                    full_description += "\n\n[英文描述]\n" + desc_en
                
                # 尝试匹配物种名称
                matched_key = name_cell.lower().strip()
                if matched_key in existing_names:
                    db_name = existing_names[matched_key]
                    # 更新数据库中的 description 字段
                    with self.connect() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE bupleurum_species SET description = ? WHERE species_name = ?",
                            (full_description, db_name)
                        )
                        if cursor.rowcount > 0:
                            results['updated'] += 1
                    results['matched'] += 1
                else:
                    results['not_found'].append(name_cell)
                    
            except Exception as e:
                results['errors'].append(f"行{idx+2}: {str(e)}")
        
        return results
        
    def get_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM bupleurum_species")
            total_species = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT growth_form) FROM bupleurum_species")
            growth_forms = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT leaf_shape) FROM bupleurum_species WHERE leaf_shape != ''")
            leaf_shapes = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT fruit_shape) FROM bupleurum_species WHERE fruit_shape != ''")
            fruit_shapes = cursor.fetchone()[0]
            
            return {
                'total_species': total_species,
                'growth_forms': growth_forms,
                'leaf_shapes': leaf_shapes,
                'fruit_shapes': fruit_shapes
            }
    
    def get_all_species_names(self) -> set:
        """获取所有物种名称"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT species_name FROM bupleurum_species")
            return {row[0] for row in cursor.fetchall()}
    
    def get_distinct_growth_forms(self) -> List[str]:
        """获取所有不同的株型"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT growth_form FROM bupleurum_species WHERE growth_form IS NOT NULL AND growth_form != '' ORDER BY growth_form")
            return [row[0] for row in cursor.fetchall()]
    
    def clear_database(self):
        """清空数据库"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bupleurum_species")
            conn.commit()
    
    def export_to_excel(self) -> pd.DataFrame:
        """导出数据为DataFrame"""
        with self.connect() as conn:
            df = pd.read_sql_query("SELECT * FROM bupleurum_species ORDER BY species_name", conn)
            return df

# 初始化数据库
@st.cache_resource
def get_database():
    return BupleurumMorphologyDB()

db = get_database()

def render_header():
    """渲染页头"""
    st.markdown("""
    <div class="custom-title">
        <h1 style="margin: 0;">🌿 柴胡形态特征数据库</h1>
        <p style="margin: 0; opacity: 0.9;">基于《柴胡词典2.xlsx》的形态特征数据库系统</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 统计信息
    stats = db.get_statistics()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🌱 物种总数", stats['total_species'])
    with col2:
        st.metric("📏 株型种类", stats['growth_forms'])
    with col3:
        st.metric("🍃 叶形种类", stats['leaf_shapes'])
    with col4:
        st.metric("🍎 果形种类", stats['fruit_shapes'])

def render_data_import():
    """渲染数据导入页面"""
    st.markdown("""
    <div style="background: #f0f7ff; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h2 style="margin: 0; color: #2c3e50;">📥 导入Excel数据</h2>
        <p style="margin: 0; color: #7f8c8d;">导入《柴胡词典2.xlsx》中的形态特征数据</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 显示Excel文件结构
    st.markdown("### 📋 Excel文件结构说明")
    st.markdown("""
    **字段说明：**
    1. **序号** - 编号
    2. **物种** - 物种名称（中文名或拉丁名）
    3. **株型** - 生长形态
    4. **最小/最大株高** - 植株高度范围（厘米）
    5. **根颜色** - 根的颜色
    6. **叶长度/宽度** - 叶片尺寸
    7. **叶形** - 叶片形状
    8. **叶颜色** - 叶片颜色
    9. **叶脉数** - 叶脉数量范围
    10. **花序直径** - 花序尺寸
    11. **总苞片特征** - 数量、形状、尺寸
    12. **伞幅特征** - 数量、长度
    13. **小伞形花序特征** - 直径、数量
    14. **小总苞片特征** - 数量、形状
    15. **花瓣颜色** - 花色
    16. **果实特征** - 形状、颜色
    """)
    
    # 文件上传
    st.markdown("### 📤 上传Excel文件")
    uploaded_file = st.file_uploader("选择Excel文件", type=['xlsx', 'xls'])
    
    if uploaded_file is not None:
        try:
            # 读取Excel文件 - 明确不读取索引列
            df = pd.read_excel(uploaded_file, sheet_name=0, index_col=None)
            
            # 清理DataFrame：删除任何未命名的索引列
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            
            # 处理数值列，将"未明确"转换为NaN
            numeric_columns = [col for col in df.columns if any(keyword in col for keyword in 
                                                                ['最小', '最大', '长度', '宽度', '直径', '高度', '数量', '脉数'])]
            
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col].replace('未明确', pd.NA), errors='coerce')
            
            # 显示数据预览
            st.markdown("### 👀 数据预览")
            st.dataframe(df.head(10), width='stretch')
            
            # 显示列信息
            st.markdown(f"#### 📊 数据概览")
            st.write(f"- 总行数: {len(df)}")
            st.write(f"- 列数: {len(df.columns)}")
            st.write(f"- 列名: {list(df.columns)}")
            
            # 检查必需字段
            required_fields = ['物种名称', '株型']
            missing_fields = [field for field in required_fields if field not in df.columns]
            
            if missing_fields:
                st.error(f"❌ Excel文件缺少必要字段: {', '.join(missing_fields)}")
                st.info(f"检测到的字段: {', '.join(df.columns)}")
            else:
                st.success(f"✅ 成功读取文件，共发现 {len(df)} 条记录")
                
                # 导入确认
                # 使用表单防止自动刷新
                with st.form(key="import_form"):
                    submitted = st.form_submit_button("🚀 开始导入数据", type="primary", use_container_width=True)
                    if submitted:
                        with st.spinner("正在导入数据..."):
                            result = db.import_from_excel_df(df)
                        # 将结果保存到 session_state 中，以便持久显示
                        st.session_state['import_result'] = result
                        st.rerun()  # 重新运行以显示结果
                
                # 如果有保存的导入结果，则显示
                if 'import_result' in st.session_state:
                    result = st.session_state['import_result']
                    st.markdown("### 📊 导入结果")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("总记录数", result['total'])
                    with col2:
                        st.metric("导入成功", result['success'])
                    with col3:
                        st.metric("导入失败", result['failed'])
                    with col4:
                        st.metric("重复跳过", result['duplicates'])
                    
                    if result['success'] > 0:
                        st.success(f"✅ 成功导入 {result['success']} 条记录")
                    
                    if result['failed'] > 0:
                        st.error(f"❌ 有 {result['failed']} 条记录导入失败")
                        with st.expander("查看错误详情"):
                            for error in result['errors']:
                                st.write(f"- {error}")
                    
                    # 添加一个按钮清除结果
                    if st.button("清除结果", key="clear_import_result"):
                        del st.session_state['import_result']
                        st.rerun()
        
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            results['errors'].append(f"{species_name}: {str(e)}\n{error_detail}")
            results['failed'] += 1
            
    st.markdown("---")  # 缩进4空格
    with st.expander("📖 导入表型库详细描述（点击展开）", expanded=False):  # 缩进4空格
        st.markdown("""  # 缩进8空格
        <div style="background: #f0f7ff; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
            ...
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_desc_file = st.file_uploader(  # 缩进8空格
            "选择表型库Excel文件", 
            type=['xlsx', 'xls'], 
            key="desc_uploader"
        )
        
        if uploaded_desc_file is not None:
            try:
                # 读取Excel，不指定表头行，因为第一行可能是数据（或者可能有标题行，需根据实际情况调整）
                df_desc = pd.read_excel(uploaded_desc_file, sheet_name=0, header=None)
                
                # 预览前几行
                st.markdown("### 👀 数据预览")
                st.dataframe(df_desc.head(10))
                
                st.write(f"- 总行数: {len(df_desc)}")
                st.write(f"- 列数: {len(df_desc.columns)}")
                
                # 导入确认
                if st.button("🚀 开始导入表型库描述", type="primary", key="import_desc"):
                    with st.spinner("正在匹配并更新描述..."):
                        result = db.import_descriptions_from_excel(df_desc)
                    
                    # 显示结果
                    st.markdown("### 📊 导入结果")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("总记录数", result['total'])
                    with col2:
                        st.metric("匹配更新", result['updated'])
                    with col3:
                        st.metric("未匹配", len(result['not_found']))
                    
                    if result['not_found']:
                        st.warning(f"以下名称未在数据库中找到：{', '.join(result['not_found'][:10])}" + 
                                   ("..." if len(result['not_found']) > 10 else ""))
                    
                    if result['errors']:
                        st.error("导入过程中发生错误：")
                        for err in result['errors'][:5]:
                            st.write(f"- {err}")
                    
                    st.success("✅ 描述导入完成")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ 文件读取失败: {str(e)}")
    # 数据导出
    st.markdown("---")
    st.markdown("### 📤 数据导出")
    
    if st.button("📥 导出当前数据", width='stretch'):
        try:
            df_export = db.export_to_excel()
            
            # 转换为Excel字节流
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='柴胡形态特征')
            
            st.download_button(
                label="下载Excel文件",
                data=output.getvalue(),
                file_name="柴胡形态特征数据库.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width='stretch'
            )
            
            st.success("✅ 数据导出完成，请点击上方按钮下载")
        except Exception as e:
            st.error(f"❌ 导出失败: {str(e)}")

def render_species_browser():
    """渲染物种浏览页面"""
    # 初始化重置版本号
    if 'filter_reset_version' not in st.session_state:
        st.session_state.filter_reset_version = 0

    # 辅助函数：生成动态key
    def dynamic_key(base):
        return f"{base}_v{st.session_state.filter_reset_version}"

    # 清除所有筛选条件的函数
    def clear_all_filters():
        st.session_state.filter_reset_version += 1
        st.rerun()

    st.markdown("""
    <div style="background: linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%); 
                color: #2c3e50; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h2 style="margin: 0;">🔍 物种浏览与搜索</h2>
        <p style="margin: 0; opacity: 0.9;">浏览和搜索柴胡属植物的形态特征</p>
    </div>
    """, unsafe_allow_html=True)

    # 搜索和筛选
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            "搜索物种", 
            placeholder="输入物种名称、叶形、果形等关键词...",
            key=dynamic_key("search_query")
        )
    with col2:
        search_limit = st.selectbox("显示数量", [10, 25, 50, 100], index=1, key=dynamic_key("search_limit"))

    # 高级筛选
    with st.expander("🔬 高级筛选", expanded=False):
        st.markdown("#### 植株特征")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            growth_form = st.text_input("株型", placeholder="如：多年生草本", key=dynamic_key("filter_growth_form"))
        with col2:
            root_color = st.text_input("根颜色", placeholder="如：黄色", key=dynamic_key("filter_root_color"))
        with col3:
            height = st.number_input("株高 (cm)", min_value=0.0, value=None, step=5.0, key=dynamic_key("filter_height"))
        with col4:
            st.markdown("")

        st.markdown("#### 叶片特征")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            leaf_shape = st.text_input("叶形", placeholder="如：线形、披针形", key=dynamic_key("filter_leaf_shape"))
        with col2:
            leaf_color = st.text_input("叶颜色", placeholder="如：绿色", key=dynamic_key("filter_leaf_color"))
        with col3:
            leaf_length = st.number_input("叶长度 (cm)", min_value=0.0, value=None, step=1.0, key=dynamic_key("filter_leaf_length"))
        with col4:
            leaf_width = st.number_input("叶宽度 (cm)", min_value=0.0, value=None, step=1.0, key=dynamic_key("filter_leaf_width"))

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            vein_number = st.number_input("叶脉数", min_value=0, value=None, step=1, key=dynamic_key("filter_vein_number"))
        with col2:
            st.markdown("")
        with col3:
            inflorescence_diameter = st.number_input("花序直径 (cm)", min_value=0.0, value=None, step=0.5, key=dynamic_key("filter_inflorescence_diameter"))
        with col4:
            ray_length = st.number_input("伞幅长度 (cm)", min_value=0.0, value=None, step=0.5, key=dynamic_key("filter_ray_length"))

        st.markdown("#### 总苞片特征")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            bract_number = st.text_input("总苞片数量", placeholder="如：3-5", key=dynamic_key("filter_bract_number"))
        with col2:
            bract_shape = st.text_input("总苞片形状", placeholder="如：卵形", key=dynamic_key("filter_bract_shape"))
        with col3:
            bract_length = st.number_input("总苞片长度 (cm)", min_value=0.0, value=None, step=0.5, key=dynamic_key("filter_bract_length"))
        with col4:
            ray_number = st.text_input("伞幅数量", placeholder="如：5-8", key=dynamic_key("filter_ray_number"))

        # 其他特征（请根据您的实际代码补充，这里仅作示例）
        st.markdown("#### 其他特征")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            umbellet_diameter = st.text_input("小伞形花序直径(cm)", placeholder="如：2-5", key=dynamic_key("filter_umbellet_diameter"))
        with col2:
            bracteole_number = st.text_input("小总苞片数量", placeholder="如：5", key=dynamic_key("filter_bracteole_number"))
        with col3:
            bracteole_shape = st.text_input("小总苞片形状", placeholder="如：线形", key=dynamic_key("filter_bracteole_shape"))
        with col4:
            umbellet_number = st.text_input("小伞形花序数量", placeholder="如：10-20", key=dynamic_key("filter_umbellet_number"))

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            petal_color = st.text_input("花瓣颜色", placeholder="如：黄色", key=dynamic_key("filter_petal_color"))
        with col2:
            fruit_shape = st.text_input("果形", placeholder="如：椭圆形", key=dynamic_key("filter_fruit_shape"))
        with col3:
            fruit_color = st.text_input("果颜色", placeholder="如：褐色", key=dynamic_key("filter_fruit_color"))
        with col4:
            st.markdown("")

        # 按钮区域
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        with col_btn1:
            if st.button("应用筛选", type="primary", use_container_width=True):
                st.session_state['filters_applied'] = True
        with col_btn2:
            if st.button("清除所有条件", type="secondary", use_container_width=True):
                clear_all_filters()
        # col_btn3 留空

    # 构建筛选条件（使用动态key从session_state取值）
    filters = {}
    if 'filters_applied' in st.session_state and st.session_state['filters_applied']:
        # 植株特征
        gf = st.session_state.get(dynamic_key("filter_growth_form"))
        if gf:
            filters['growth_form'] = gf
        rc = st.session_state.get(dynamic_key("filter_root_color"))
        if rc:
            filters['root_color'] = rc
        h = st.session_state.get(dynamic_key("filter_height"))
        if h is not None:
            filters['height'] = h

        # 叶片特征
        ls = st.session_state.get(dynamic_key("filter_leaf_shape"))
        if ls:
            filters['leaf_shape'] = ls
        lc = st.session_state.get(dynamic_key("filter_leaf_color"))
        if lc:
            filters['leaf_color'] = lc
        ll = st.session_state.get(dynamic_key("filter_leaf_length"))
        if ll is not None:
            filters['leaf_length'] = ll
        lw = st.session_state.get(dynamic_key("filter_leaf_width"))
        if lw is not None:
            filters['leaf_width'] = lw
        vn = st.session_state.get(dynamic_key("filter_vein_number"))
        if vn is not None:
            filters['vein_number'] = vn
        idm = st.session_state.get(dynamic_key("filter_inflorescence_diameter"))
        if idm is not None:
            filters['inflorescence_diameter'] = idm
        rl = st.session_state.get(dynamic_key("filter_ray_length"))
        if rl is not None:
            filters['ray_length'] = rl

        # 总苞片特征
        bn = st.session_state.get(dynamic_key("filter_bract_number"))
        if bn:
            filters['bract_number'] = bn
        bs = st.session_state.get(dynamic_key("filter_bract_shape"))
        if bs:
            filters['bract_shape'] = bs
        bl = st.session_state.get(dynamic_key("filter_bract_length"))
        if bl is not None:
            filters['bract_length'] = bl
        rn = st.session_state.get(dynamic_key("filter_ray_number"))
        if rn:
            filters['ray_number'] = rn

        # 其他特征（根据您的实际字段补充）
        ud = st.session_state.get(dynamic_key("filter_umbellet_diameter"))
        if ud:
            filters['umbellet_diameter'] = ud  # 注意数据库列名
        ben = st.session_state.get(dynamic_key("filter_bracteole_number"))
        if ben:
            filters['bracteole_number'] = ben
        bes = st.session_state.get(dynamic_key("filter_bracteole_shape"))
        if bes:
            filters['bracteole_shape'] = bes
        un = st.session_state.get(dynamic_key("filter_umbellet_number"))
        if un:
            filters['umbellet_number'] = un
        pc = st.session_state.get(dynamic_key("filter_petal_color"))
        if pc:
            filters['petal_color'] = pc
        fs = st.session_state.get(dynamic_key("filter_fruit_shape"))
        if fs:
            filters['fruit_shape'] = fs
        fc = st.session_state.get(dynamic_key("filter_fruit_color"))
        if fc:
            filters['fruit_color'] = fc

    # 执行搜索
    results = db.search_species(search_query, filters) if search_query or filters else db.get_all_species(search_limit)
    # 按中文优先排序
    results.sort(key=chinese_first_key)

    # 显示结果
    if not results:
        st.warning("🔍 未找到匹配的物种。")
        return

    st.success(f"✅ 找到 {len(results)} 个物种")

    view_mode = st.radio(
        "显示模式", 
        ["卡片视图", "表格视图", "摘要视图"], 
        horizontal=True,
        index=2,  # 默认摘要视图
        key=dynamic_key("view_mode")
    )
    if view_mode == "卡片视图":
        display_species_cards(results)
    elif view_mode == "表格视图":
        display_species_table(results)
    else:
        display_species_summary(results)


def display_species_cards(species_list: List[Dict[str, Any]]):
    """以卡片形式显示物种"""
    cols = st.columns(2)
    
    for idx, species in enumerate(species_list):
        with cols[idx % len(cols)]:
            with st.container():
                # 计算株高范围
                height_range = ""
                min_height = species.get('min_height_cm')
                max_height = species.get('max_height_cm')
                if min_height is not None and max_height is not None:
                    height_range = f"{min_height}-{max_height} cm"
                elif min_height is not None:
                    height_range = f"≥{min_height} cm"
                elif max_height is not None:
                    height_range = f"≤{max_height} cm"
                
                # 处理叶脉数
                vein_range = ""
                min_vein = species.get('min_vein_number')
                max_vein = species.get('max_vein_number')
                if min_vein is not None and max_vein is not None:
                    vein_range = f"{min_vein}-{max_vein}"
                elif min_vein is not None:
                    vein_range = f"≥{min_vein}"
                elif max_vein is not None:
                    vein_range = f"≤{max_vein}"
                
                st.markdown(f"""
                <div class="species-card">
                    <h3>{species['species_name']}</h3>
                    <p><strong>📏 株型:</strong> {species.get('growth_form', '未明确') or '未明确'}</p>
                    <p><strong>📐 株高:</strong> {height_range if height_range else '未明确'}</p>
                    <p><strong>🍃 叶形:</strong> {truncate_text(species.get('leaf_shape', '未明确') or '未明确', 20)}</p>
                    <p><strong>🌸 花色:</strong> {species.get('petal_color', '未明确') or '未明确'}</p>
                    <p><strong>🍎 果形:</strong> {species.get('fruit_shape', '未明确') or '未明确'}</p>
                    <div style="margin-top: 0.5rem;">
                        <span class="feature-tag">ID: {species['id']}</span>
                        {f'<span class="feature-tag">叶脉: {vein_range}</span>' if vein_range else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 新增：如果存在描述，显示一个可折叠区域
                desc = species.get('description', '')
                if desc and not pd.isna(desc):
                    with st.expander("📖 详细描述"):
                        st.write(desc)
                
                if st.button("查看详情", key=f"view_{species['id']}", width='stretch'):
                    st.session_state['selected_species'] = species['id']
                    st.rerun()

def display_species_table(species_list: List[Dict[str, Any]]):
    """以表格形式显示物种"""
    # 准备表格数据
    table_data = []
    for species in species_list:
        table_data.append({
            "ID": species['id'],
            "物种名称": species['species_name'],
            "株型": species.get('growth_form', '') or '',
            "株高范围(cm)": f"{species.get('min_height_cm', '')}-{species.get('max_height_cm', '')}" if species.get('min_height_cm') or species.get('max_height_cm') else '',
            "叶形": species.get('leaf_shape', '') or '',
            "花色": species.get('petal_color', '') or '',
            "果形": species.get('fruit_shape', '') or '',
            "叶脉数": f"{species.get('min_vein_number', '')}-{species.get('max_vein_number', '')}" if species.get('min_vein_number') or species.get('max_vein_number') else ''
        })
    
    df = pd.DataFrame(table_data)
    st.dataframe(df, width='stretch', hide_index=True)

def display_species_summary(species_list: List[Dict[str, Any]]):
    """以摘要形式显示物种"""
    for species in species_list:
        with st.expander(f"🌿 {species['species_name']} - {species.get('growth_form', '') or ''}"):
            # 原有两列内容保持不变...
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📏 植株特征")
                min_height = species.get('min_height_cm')
                max_height = species.get('max_height_cm')
                height_text = f"{min_height}-{max_height} cm" if min_height is not None and max_height is not None else '未明确'
                st.write(f"**株高:** {height_text}")
                st.write(f"**根颜色:** {species.get('root_color', '未明确') or '未明确'}")
                
                st.markdown("#### 🍃 叶片特征")
                st.write(f"**叶形:** {species.get('leaf_shape', '未明确') or '未明确'}")
                leaf_min_len = species.get('leaf_min_length_cm')
                leaf_max_len = species.get('leaf_max_length_cm')
                leaf_min_wid = species.get('leaf_min_width_cm')
                leaf_max_wid = species.get('leaf_max_width_cm')
                leaf_size_text = f"{leaf_min_len}-{leaf_max_len} cm × {leaf_min_wid}-{leaf_max_wid} cm" if all(v is not None for v in [leaf_min_len, leaf_max_len, leaf_min_wid, leaf_max_wid]) else '未明确'
                st.write(f"**叶尺寸:** {leaf_size_text}")
                st.write(f"**叶颜色:** {species.get('leaf_color', '未明确') or '未明确'}")
                min_vein = species.get('min_vein_number')
                max_vein = species.get('max_vein_number')
                vein_text = f"{min_vein}-{max_vein}" if min_vein is not None and max_vein is not None else '未明确'
                st.write(f"**叶脉数:** {vein_text}")
            
            with col2:
                st.markdown("#### 🌸 花序特征")
                min_inflorescence = species.get('min_inflorescence_diameter_cm')
                max_inflorescence = species.get('max_inflorescence_diameter_cm')
                inflorescence_text = f"{min_inflorescence}-{max_inflorescence} cm" if min_inflorescence is not None and max_inflorescence is not None else '未明确'
                st.write(f"**花序直径:** {inflorescence_text}")
                st.write(f"**总苞片:** {species.get('bract_number', '') or ''}个, {species.get('bract_shape', '') or ''}, {species.get('min_bract_length_cm', '')}-{species.get('max_bract_length_cm', '')} cm")
                st.write(f"**伞幅:** {species.get('ray_number', '') or ''}个, {species.get('min_ray_length_cm', '')}-{species.get('max_ray_length_cm', '')} cm")
                # 处理小伞形花序直径范围
                min_d = species.get('umbellet_diameter_min_cm')
                max_d = species.get('umbellet_diameter_max_cm')
                if min_d is not None and max_d is not None:
                    dia_text = f"{min_d}-{max_d} cm"
                elif min_d is not None:
                    dia_text = f"≥{min_d} cm"
                elif max_d is not None:
                    dia_text = f"≤{max_d} cm"
                else:
                    dia_text = "未明确"
                st.write(f"**小伞形花序:** 直径{dia_text}, {species.get('umbellet_number', '') or ''}个")
                
                st.markdown("#### 🍎 果实特征")
                st.write(f"**果形:** {species.get('fruit_shape', '未明确') or '未明确'}")
                st.write(f"**果颜色:** {species.get('fruit_color', '未明确') or '未明确'}")
                            # 新增：如果有描述，在全宽区域显示
            desc = species.get('description', '')
            if desc and not pd.isna(desc):
                st.markdown("#### 📖 详细描述")
                st.write(desc)

def render_species_detail(species_id: int):
    """渲染物种详情页面"""
    # 获取物种数据
    all_species = db.get_all_species()
    species = next((s for s in all_species if s['id'] == species_id), None)
    
    if not species:
        st.error("未找到指定的物种")
        return
    
    # 返回按钮
    if st.button("← 返回", width='stretch'):
        if 'selected_species' in st.session_state:
            del st.session_state['selected_species']
        st.rerun()
    
    # 物种详情卡片
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h1 style="margin: 0;">{species['species_name']}</h1>
        <p style="margin: 0; opacity: 0.9;">ID: {species['id']} | 序号: {species.get('serial_number', 'N/A')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 创建标签页时增加一个
    tabs = st.tabs(["📋 基本信息", "🌱 植株特征", "🍃 叶片特征", "🌸 花序特征", "🍎 果实特征", "📖 详细描述", "📊 完整数据"])
    with tabs[0]:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("株型", species.get('growth_form', '未明确') or '未明确')
        with col2:
            min_height = species.get('min_height_cm')
            max_height = species.get('max_height_cm')
            height_range = f"{min_height}-{max_height} cm" if min_height is not None and max_height is not None else '未明确'
            st.metric("株高范围", height_range)
        with col3:
            st.metric("根颜色", species.get('root_color', '未明确') or '未明确')
    
    with tabs[1]:
        st.markdown('<div class="feature-group">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 📏 植株尺寸")
            st.write(f"**最小株高:** {species.get('min_height_cm', '未明确') or '未明确'} cm")
            st.write(f"**最大株高:** {species.get('max_height_cm', '未明确') or '未明确'} cm")
            st.write(f"**根颜色:** {species.get('root_color', '未明确') or '未明确'}")
        
        with col2:
            st.markdown("##### 🏷️ 其他特征")
            # 这里可以添加更多植株特征
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[2]:
        st.markdown('<div class="feature-group">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 📐 叶片尺寸")
            st.write(f"**最小长度:** {species.get('leaf_min_length_cm', '未明确') or '未明确'} cm")
            st.write(f"**最大长度:** {species.get('leaf_max_length_cm', '未明确') or '未明确'} cm")
            st.write(f"**最小宽度:** {species.get('leaf_min_width_cm', '未明确') or '未明确'} cm")
            st.write(f"**最大宽度:** {species.get('leaf_max_width_cm', '未明确') or '未明确'} cm")
        
        with col2:
            st.markdown("##### 🎨 叶片特征")
            st.write(f"**叶形:** {species.get('leaf_shape', '未明确') or '未明确'}")
            st.write(f"**叶颜色:** {species.get('leaf_color', '未明确') or '未明确'}")
            st.write(f"**最小叶脉数:** {species.get('min_vein_number', '未明确') or '未明确'}")
            st.write(f"**最大叶脉数:** {species.get('max_vein_number', '未明确') or '未明确'}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[3]:
        st.markdown('<div class="feature-group">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("##### 🌸 花序特征")
            st.write(f"**最小花序直径:** {species.get('min_inflorescence_diameter_cm', '未明确') or '未明确'} cm")
            st.write(f"**最大花序直径:** {species.get('max_inflorescence_diameter_cm', '未明确') or '未明确'} cm")
            st.write(f"**花瓣颜色:** {species.get('petal_color', '未明确') or '未明确'}")
        
        with col2:
            st.markdown("##### 🍃 总苞片")
            st.write(f"**数量:** {species.get('bract_number', '未明确') or '未明确'}")
            st.write(f"**形状:** {species.get('bract_shape', '未明确') or '未明确'}")
            st.write(f"**最小长度:** {species.get('min_bract_length_cm', '未明确') or '未明确'} cm")
            st.write(f"**最大长度:** {species.get('max_bract_length_cm', '未明确') or '未明确'} cm")
        
        with col3:
            st.markdown("##### ☂️ 伞幅特征")
            st.write(f"**数量:** {species.get('ray_number', '未明确') or '未明确'}")
            st.write(f"**最小长度:** {species.get('min_ray_length_cm', '未明确') or '未明确'} cm")
            st.write(f"**最大长度:** {species.get('max_ray_length_cm', '未明确') or '未明确'} cm")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="feature-group">', unsafe_allow_html=True)
        col4, col5 = st.columns(2)
        with col4:
            st.markdown("##### 🌼 小伞形花序")
            st.write(f"**直径:** {species.get('umbellet_diameter_cm', '未明确') or '未明确'} cm")
            st.write(f"**数量:** {species.get('umbellet_number', '未明确') or '未明确'}")
        
        with col5:
            st.markdown("##### 🍂 小总苞片")
            st.write(f"**数量:** {species.get('bracteole_number', '未明确') or '未明确'}")
            st.write(f"**形状:** {species.get('bracteole_shape', '未明确') or '未明确'}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[4]:
        st.markdown('<div class="feature-group">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 🍎 果实形状")
            st.write(f"**果形:** {species.get('fruit_shape', '未明确') or '未明确'}")
        with col2:
            st.markdown("##### 🎨 果实颜色")
            st.write(f"**果颜色:** {species.get('fruit_color', '未明确') or '未明确'}")
        st.markdown('</div>', unsafe_allow_html=True)
    with tabs[5]:  # 新增的详细描述标签
        st.markdown('<div class="feature-group">', unsafe_allow_html=True)
        desc = species.get('description', '')
        if desc and not pd.isna(desc):
            st.markdown(desc)
        else:
            st.info("暂无详细描述")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with tabs[6]:
        # 显示完整数据
        st.markdown("### 📊 完整数据记录")
        
        # 创建数据表
        data_items = [
            ("ID", species['id']),
            ("序号", species.get('serial_number', '')),
            ("物种名称", species['species_name']),
            ("是否亚种", species.get('is_subspecies', '')),
            ("原种名称", species.get('original_species', '')),
            ("亚种编号", species.get('subspecies_no', '')),
            ("株型", species.get('growth_form', '')),
            ("最小株高(cm)", species.get('min_height_cm', '')),
            ("最大株高(cm)", species.get('max_height_cm', '')),
            ("根颜色", species.get('root_color', '')),
            ("叶形", species.get('leaf_shape', '')),
            ("叶位置", species.get('leaf_position', '')),
            ("叶最小长度(cm)", species.get('leaf_min_length_cm', '')),
            ("叶最大长度(cm)", species.get('leaf_max_length_cm', '')),
            ("叶最小宽度(cm)", species.get('leaf_min_width_cm', '')),   # 原为 mm
            ("叶最大宽度(cm)", species.get('leaf_max_width_cm', '')),
            ("叶颜色", species.get('leaf_color', '')),
            ("最小叶脉数", species.get('min_vein_number', '')),
            ("最大叶脉数", species.get('max_vein_number', '')),
            ("叶独特特征", species.get('leaf_unique_features', '')),
            ("植株特征", species.get('plant_features', '')),
            ("果实特征", species.get('fruit_features', '')),
            ("最小花序直径(cm)", species.get('min_inflorescence_diameter_cm', '')),
            ("最大花序直径(cm)", species.get('max_inflorescence_diameter_cm', '')),
            ("总苞片数量", species.get('bract_number', '')),
            ("总苞片形状", species.get('bract_shape', '')),
            ("总苞片最小长度(cm)", species.get('min_bract_length_cm', '')),   # 原为 mm
            ("总苞片最大长度(cm)", species.get('max_bract_length_cm', '')),
            ("伞辐数量", species.get('ray_number', '')),
            ("最小伞辐长度(cm)", species.get('min_ray_length_cm', '')),
            ("最大伞辐长度(cm)", species.get('max_ray_length_cm', '')),
            ("小伞形花序最小直径(cm)", species.get('umbellet_diameter_min_cm', '')),   # 新增
            ("小伞形花序最大直径(cm)", species.get('umbellet_diameter_max_cm', '')),
            ("小总苞片数量", species.get('bracteole_number', '')),
            ("小总苞片形状", species.get('bracteole_shape', '')),
            ("小伞形花序数量", species.get('umbellet_number', '')),
            ("花瓣颜色", species.get('petal_color', '')),
            ("果形状", species.get('fruit_shape', '')),
            ("果颜色", species.get('fruit_color', '')),
            ("创建时间", species.get('created_at', ''))
        ]
        
        # 显示数据表格
        html_table = """
        <table class="data-table" style="width:100%">
            <tr>
                <th style="width:30%">字段</th>
                <th style="width:70%">值</th>
            </tr>
        """
        
        for field, value in data_items:
            if value not in [None, '', 'nan', '未明确']:
                display_value = value if value is not None else ''
                html_table += f"""
                <tr>
                    <td><strong>{field}</strong></td>
                    <td>{display_value}</td>
                </tr>
                """
        
        html_table += "</table>"
        st.markdown(html_table, unsafe_allow_html=True)

def render_data_analysis():
    """渲染数据分析页面"""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); 
                color: #2c3e50; padding: 1.5rem; border-radius: 10px; margin-bottom: 1.rem;">
        <h2 style="margin: 0;">📊 数据分析</h2>
        <p style="margin: 0; opacity: 0.9;">柴胡形态特征统计分析</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 获取所有数据
    all_species = db.get_all_species()
    
    if not all_species:
        st.info("📭 数据库为空，请先导入数据")
        return
    
    # 基本统计
    st.markdown("### 📈 基本统计")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # 株高统计
        heights = []
        for species in all_species:
            if species.get('max_height_cm'):
                heights.append(species['max_height_cm'])
        
        if heights:
            avg_height = sum(heights) / len(heights)
            st.metric("平均最大株高", f"{avg_height:.1f} cm")
    
    with col2:
        # 叶脉数统计
        vein_counts = []
        for species in all_species:
            if species.get('max_vein_number'):
                vein_counts.append(species['max_vein_number'])
        
        if vein_counts:
            avg_veins = sum(vein_counts) / len(vein_counts)
            st.metric("平均最大叶脉数", f"{avg_veins:.1f}")
    
    with col3:
        # 株型分布
        growth_forms = {}
        for species in all_species:
            form = species.get('growth_form', '未明确')
            if form:
                growth_forms[form] = growth_forms.get(form, 0) + 1
        
        if growth_forms:
            common_form = max(growth_forms.items(), key=lambda x: x[1])[0]
            st.metric("最常见株型", common_form)
        else:
            st.metric("最常见株型", "无数据")
    
    with col4:
        # 花色分布
        colors = {}
        for species in all_species:
            color = species.get('petal_color', '未明确')
            if color:
                colors[color] = colors.get(color, 0) + 1
        
        if colors:
            common_color = max(colors.items(), key=lambda x: x[1])[0]
            st.metric("最常见花色", common_color)
        else:
            st.metric("最常见花色", "无数据")
    
    # 特征分布分析
    st.markdown("### 📊 特征分布")
    
    tab1, tab2, tab3 = st.tabs(["株型分布", "叶形分布", "果形分布"])
    
    with tab1:
        # 株型分布
        growth_form_counts = {}
        for species in all_species:
            form = species.get('growth_form', '未明确')
            if form:
                growth_form_counts[form] = growth_form_counts.get(form, 0) + 1
        
        if growth_form_counts:
            df_growth = pd.DataFrame({
                '株型': list(growth_form_counts.keys()),
                '数量': list(growth_form_counts.values())
            }).sort_values('数量', ascending=False)
            
            st.bar_chart(df_growth.set_index('株型'))
    
    with tab2:
        # 叶形分布
        leaf_shape_counts = {}
        for species in all_species:
            shape = species.get('leaf_shape', '未明确')
            if shape and shape != '未明确':
                # 处理多个叶形的情况
                shapes = [s.strip() for s in str(shape).split('、') if s.strip()]
                for s in shapes:
                    leaf_shape_counts[s] = leaf_shape_counts.get(s, 0) + 1
        
        if leaf_shape_counts:
            df_leaf = pd.DataFrame({
                '叶形': list(leaf_shape_counts.keys()),
                '数量': list(leaf_shape_counts.values())
            }).sort_values('数量', ascending=False).head(10)
            
            st.bar_chart(df_leaf.set_index('叶形'))
    
    with tab3:
        # 果形分布
        fruit_shape_counts = {}
        for species in all_species:
            shape = species.get('fruit_shape', '未明确')
            if shape:
                fruit_shape_counts[shape] = fruit_shape_counts.get(shape, 0) + 1
        
        if fruit_shape_counts:
            df_fruit = pd.DataFrame({
                '果形': list(fruit_shape_counts.keys()),
                '数量': list(fruit_shape_counts.values())
            }).sort_values('数量', ascending=False)
            
            st.bar_chart(df_fruit.set_index('果形'))

def render_management():
    """渲染管理页面"""
    st.markdown("""
    <div style="background: #fff3e0; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h2 style="margin: 0; color: #e65100;">⚙️ 系统管理</h2>
        <p style="margin: 0; color: #f57c00;">数据库维护与管理</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["数据库状态", "数据维护", "系统设置"])
    
    with tab1:
        stats = db.get_statistics()
        
        st.metric("🌱 物种总数", stats['total_species'])
        st.metric("📊 数据库状态", "正常" if stats['total_species'] > 0 else "空")
        
        # 显示所有物种名称
        all_species = db.get_all_species()
        if all_species:
            st.markdown("### 📋 物种列表")
            species_names = [f"{s['id']}. {s['species_name']}" for s in all_species]
            st.write(", ".join(species_names))
    
    with tab2:
        st.warning("⚠️ 谨慎操作以下功能！")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 优化数据库", width='stretch'):
                try:
                    with db.connect() as conn:
                        cursor = conn.cursor()
                        cursor.execute("VACUUM")
                        conn.commit()
                    st.success("✅ 数据库优化完成")
                except Exception as e:
                    st.error(f"❌ 优化失败：{str(e)}")
        
        with col2:
            if st.button("🗑️ 清空缓存", width='stretch'):
                st.cache_resource.clear()
                st.success("✅ 缓存已清理")
        
        # 危险操作
        with st.expander("🚨 危险操作", expanded=False):
            st.error("以下操作不可逆！")
            
            if st.button("清空数据库", type="secondary", width='stretch'):
                st.warning("这将删除所有数据！")
                confirm = st.checkbox("我确认要清空数据库")
                
                if confirm:
                    if st.button("确认清空", type="primary", width='stretch'):
                        db.clear_database()
                        st.success("✅ 数据库已清空")
                        st.rerun()
    
    with tab3:
        st.markdown("### ⚙️ 系统设置")
        
        # 显示版本信息
        st.write("**系统版本:** 柴胡形态特征数据库 v2.0")
        st.write("**数据库路径:** bupleurum_morphology.db")
        st.write("**数据来源:** 柴胡词典2.xlsx")
        
        # 导出功能
        st.markdown("### 📤 数据导出")
        
        if st.button("导出完整数据", width='stretch'):
            try:
                df_export = db.export_to_excel()
                
                # 显示数据预览
                st.dataframe(df_export.head(), width='stretch')
                
                # 转换为CSV
                csv_data = df_export.to_csv(index=False, encoding='utf-8-sig')
                
                st.download_button(
                    label="下载CSV文件",
                    data=csv_data,
                    file_name="柴胡形态特征数据库.csv",
                    mime="text/csv",
                    width='stretch'
                )
                
                st.success("✅ 数据导出完成")
            except Exception as e:
                st.error(f"❌ 导出失败: {str(e)}")

def truncate_text(text: str, max_length: int) -> str:
    """截断文本并添加省略号"""
    if not text:
        return "未明确"
    if len(str(text)) <= max_length:
        return str(text)
    return str(text)[:max_length] + "..."

def render_about_page():
    """渲染关于页面"""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%); 
                color: white; padding: 2rem; border-radius: 10px; margin-bottom: 1.5rem;">
        <h1 style="margin: 0; text-align: center;">🌿 柴胡形态特征数据库系统</h1>
        <p style="margin: 0.5rem 0; text-align: center; opacity: 0.9;">v2.0.0 | 基于Streamlit构建</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📖 系统介绍")
        st.markdown("""
        柴胡形态特征数据库系统是一个专门为植物学家、中医药研究者和植物爱好者设计的Web应用，
        用于管理、查询和分析柴胡属植物的详细形态特征数据。
        
        **数据来源：**
        本系统数据基于《柴胡词典2.xlsx》整理，涵盖柴胡属植物的30多个形态特征，
        包括植株、叶片、花序、果实等多个方面的详细描述。
        
        **主要特性：**
        - 📊 完整的形态特征数据管理
        - 🔍 多条件高级搜索和筛选
        - 📈 数据统计和可视化分析
        - 📱 响应式设计，支持移动设备
        - 📥 支持Excel数据导入导出
        """)
    
    with col2:
        st.markdown("### 🛠️ 技术架构")
        st.markdown("""
        **前端技术：**
        - Streamlit框架
        - 响应式CSS设计
        - 移动端优先设计
        
        **后端技术：**
        - SQLite数据库
        - Pandas数据处理
        - 多条件查询优化
        
        **数据字段：**
        系统支持30多个形态特征字段，包括：
        - 植株特征：株型、株高、根颜色
        - 叶片特征：叶形、叶尺寸、叶脉数
        - 花序特征：花序直径、苞片特征
        - 果实特征：果形、果颜色
        
        **部署方式：**
        - 支持本地运行
        - 支持云部署
        - 支持Docker容器化
        """)
    
    st.markdown("---")
    
    st.markdown("### 📱 使用指南")
    col_guide1, col_guide2, col_guide3 = st.columns(3)
    
    with col_guide1:
        st.markdown("#### 1. 数据导入")
        st.markdown("""
        准备Excel文件
        上传到系统
        自动解析数据
        """)
    
    with col_guide2:
        st.markdown("#### 2. 数据浏览")
        st.markdown("""
        按名称搜索
        按特征筛选
        查看详细数据
        """)
    
    with col_guide3:
        st.markdown("#### 3. 数据分析")
        st.markdown("""
        查看统计信息
        分析特征分布
        导出分析结果
        """)

def main():
    """主应用"""
    # 侧边栏导航
    with st.sidebar:
        st.title("🌿 导航菜单")
        
        page_options = [
            "🏠 首页概览",
            "🔍 物种浏览",
            "📥 数据导入", 
            "📊 数据分析",
            "⚙️ 系统管理",
            "ℹ️ 关于系统"
        ]
        
        page = st.radio("选择页面", page_options, index=0)
        
        st.markdown("---")
        
        # 快速统计
        stats = db.get_statistics()
        st.markdown("### 📊 快速统计")
        st.write(f"🌱 物种数: **{stats['total_species']}**")
        st.write(f"📏 株型种类: **{stats['growth_forms']}**")
        st.write(f"🍃 叶形种类: **{stats['leaf_shapes']}**")
        
        st.markdown("---")
        
        if st.button("🔄 刷新页面", width='stretch'):
            st.rerun()
    
    # 根据选择显示页面
    render_header()
    
    if page == "🏠 首页概览":
        # 显示欢迎信息和快速操作
        st.markdown("""
        ## 欢迎使用柴胡形态特征数据库系统
        
        本系统基于《柴胡词典2.xlsx》构建，专门用于管理和查询柴胡属植物的形态特征数据。
        
        **主要功能：**
        - 🔍 **物种浏览与搜索**：按名称、特征搜索柴胡物种
        - 📥 **数据导入**：导入Excel格式的柴胡形态特征数据
        - 📊 **数据分析**：统计分析柴胡的形态特征分布
        - ⚙️ **系统管理**：数据库维护和管理
        
        **快速开始：**
        1. 在侧边栏选择"数据导入"页面
        2. 上传您的Excel文件（柴胡词典2.xlsx）
        3. 开始浏览和分析数据
        """)
         
        # 显示最近添加的物种
        recent_species = db.get_all_species(limit=6)
        if recent_species:
            # 按中文在前、英文在后排序
            recent_species.sort(key=chinese_first_key)
            st.markdown("### 📚 最近添加的物种")
            display_species_cards(recent_species)
    
    elif page == "🔍 物种浏览":
        render_species_browser()
        
        # 如果有选中的物种，显示详情
        if 'selected_species' in st.session_state:
            render_species_detail(st.session_state['selected_species'])
    
    elif page == "📥 数据导入":
        render_data_import()
    
    elif page == "📊 数据分析":
        render_data_analysis()
    
    elif page == "⚙️ 系统管理":
        render_management()
    
    elif page == "ℹ️ 关于系统":
        render_about_page()

if __name__ == "__main__":
    main()





















