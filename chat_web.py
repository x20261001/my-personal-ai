import streamlit as st
from openai import OpenAI
import json
import os
from pypdf import PdfReader
import docx
from streamlit_mic_recorder import speech_to_text

st.set_page_config(page_title="我的专属AI", page_icon="🤖")
st.title("🤖 我的专属 AI 助手（全能版）")


client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

# 1. 定义文件路径（必须放在最前面）
HISTORY_FILE = "chat_history.json"
PROFILE_FILE = "user_profile.txt"  # 核心档案文件

# 2. 读取历史记忆（加入了档案读取逻辑）
if "messages" not in st.session_state:
    profile_text = ""
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            profile_text = f.read()

    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            st.session_state.messages = json.load(f)
    else:
        st.session_state.messages = [
            {"role": "system", "content": f"你是一个耐心的AI助手。这是用户的专属背景档案，请参考它来回答：\n{profile_text}"}
        ]

# ====== 3. 新增：侧边栏功能（归档并开启新对话） ======
with st.sidebar:
    st.write("⚙️ **记忆管理**")
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            st.info(f"当前专属档案：\n{f.read()[:200]}...")
    
    if st.button("📦 归档并开启新对话"):
        with st.spinner("正在提炼你的个人档案，请稍候..."):
            all_text = ""
            for msg in st.session_state.messages:
                if msg["role"] != "system":
                    all_text += f"{msg['role']}：{msg['content']}\n"
            
            if len(all_text) < 50:
                st.warning("聊天记录太少，先多聊几句再归档哦！")
            else:
                prompt = f"""
                你是一个记忆提炼助手。请阅读以下我和AI的历史聊天记录，提取核心信息。
                总结成一段不超过400字的“用户专属档案”。
                重点包含：我的家庭情况、正在学什么、做过哪些重要事、关心什么话题。
                聊天记录如下：
                {all_text[:15000]}
                """
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}]
                )
                profile_summary = response.choices[0].message.content

                with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                    f.write(profile_summary)

                st.session_state.messages = [
                    {"role": "system", "content": f"你是一个耐心的AI助手。这是用户的专属背景档案，请参考它来回答：\n{profile_summary}"}
                ]
                with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.messages, f, ensure_ascii=False)

                st.success("档案提炼并归档成功！记忆已焕然一新。")
                st.rerun()
   
# =================================================



# ====== 5. 渲染历史对话 ======
for msg in st.session_state.messages[1:]:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# 6. 接收用户输入（文本与语音并排）
st.write("---")
col1, col2 = st.columns(2)
with col1:
    st.write("📂 **上传并解析文档**")
with col2:
    st.write("🎤 **语音输入**")
    voice_text = speech_to_text(language='zh-CN', start_prompt="🎤 点击说话", stop_prompt="🔴 停止录音", key='my_stt')

# ====== 6. 接收用户输入 ======
# ====== 4. 文档上传与切片（RAG的第一步） ======
uploaded_file = st.file_uploader("📂 上传你的文档（PDF或Word），AI会存入本地知识库", type=["pdf", "docx"])
if uploaded_file is not None:
    if st.button("解析文档并存入知识库"):
        text_content = ""
        if uploaded_file.name.endswith(".pdf"):
            reader = PdfReader(uploaded_file)
            for page in reader.pages:
                if page.extract_text():
                    text_content += page.extract_text() + "\n"
        elif uploaded_file.name.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            for para in doc.paragraphs:
                text_content += para.text + "\n"

        if len(text_content) < 50:
            st.error("无法提取文字（可能是扫描件图片），请改用文字版PDF或Word。")
        else:
            # 核心：把长文档切成 500 字一个的小块
            chunk_size = 500
            chunks = [text_content[i:i+chunk_size] for i in range(0, len(text_content), chunk_size)]
            st.session_state.doc_chunks = chunks
            st.success(f"文档解析成功！已切分为 {len(chunks)} 个知识片段。可以开始提问了。")
# ====== 儿童游戏推荐助手（网页版） ======
st.write("---")  # 分割线
st.subheader("🎮 儿童游戏推荐助手")
kid_age = st.number_input("请输入孩子的年龄：", min_value=0.0, max_value=18.0, value=2.5, step=0.5)

if st.button("给我推荐！"):
    if kid_age >= 6:
        st.success("推荐带他玩：Scratch 图形化编程！")
    elif kid_age >= 3:
        st.success("推荐带他玩：乐高积木！")
    else:
        st.success("推荐带他玩：亲子互动绘本！")

# 下面是聊天输入框（保留你原有的）
prompt = st.chat_input("请输入你想说的话...")

# ====== 7. RAG检索与AI回复 ======
if prompt:
    # 1. 显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # 2. 检索（如果你之前传过文档，就在这里搜索）
    context = ""
    if "doc_chunks" in st.session_state and st.session_state.doc_chunks:
        import jieba
        # 把用户的问题分词
        question_words = set(jieba.cut(prompt))
        scored_chunks = []
        
        # 去每个片段里找相同的词
        for chunk in st.session_state.doc_chunks:
            chunk_words = set(jieba.cut(chunk))
            # 计算重叠词数量作为相关性分数
            score = len(question_words.intersection(chunk_words))
            scored_chunks.append((score, chunk))
        
        # 按分数从高到低排序，取前3个最相关的片段
        scored_chunks.sort(reverse=True, key=lambda x: x[0])
        top_chunks = [chunk for score, chunk in scored_chunks[:3] if score > 0]
        
        if top_chunks:
            context = "\n\n".join(top_chunks)
            print("【系统提示】成功检索到相关文档片段！")

    # 3. 构建发给 AI 的消息
    messages_for_ai = st.session_state.messages.copy()
    if context:
        # 如果检索到了相关内容，作为系统提示注入
        messages_for_ai.append({
            "role": "system", 
            "content": f"以下是与用户问题最相关的文档片段，请根据这些片段回答：\n\n{context}\n\n如果片段中没有答案，请诚实地告诉用户。"
        })

    # 4. 调用 API
    with st.spinner("AI正在思考..."):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages_for_ai
        )
        reply = response.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.write(reply)

    # 5. 保存记忆
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)