# --- Supabase Database Connection (Fixed Cached Widget Warning) ---
@st.cache_resource
def init_supabase(url: str, key: str) -> Client:
    """Ye function purely database client initialize karega aur isme koi widget nahi hoga."""
    return create_client(url, key)

# 1. Pehle variables ko initialize karein
url, key = None, None

# 2. Check karein agar Secrets available hain
if "supabase" in st.secrets:
    url = st.secrets["supabase"].get("url")
    key = st.secrets["supabase"].get("key")

# 3. Fallback: Agar secrets cloud par nahi mile, toh widget ko cache ke BAAHAR chalayein
if not url or not key:
    st.sidebar.warning("⚠️ Secrets automatically nahi mile! Niche manually details dalein:")
    url = st.sidebar.text_input("Supabase Project URL:", "https://tpbbngotolgthytgjarp.supabase.co", key="sb_url_manual")
    key = st.sidebar.text_input("Supabase Anon Key:", type="password", key="sb_key_manual")

# 4. Agar user ne abhi tak sidebar mein key nahi daali hai, toh app ko rokein
if not url or not key:
    st.info("👋 Welcome! Kripya dashboard shuru karne ke liye sidebar mein Supabase Anon Key dalein.")
    st.stop()

# 5. Safe Initialize Client (Pass parameters to cached function)
try:
    supabase = init_supabase(url, key)
except Exception as e:
    st.error(f"Supabase connection initialize karne mein dikkat aayi: {e}")
    st.stop()
