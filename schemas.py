from typing import TypedDict,List
import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.vectorstores import Chroma
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_huggingface import HuggingFaceEmbeddings
import time
from queries import convo_db_creation_query, convo_insertion_query,convo_cleanup_query

load_dotenv()

import warnings
import os
warnings.filterwarnings("ignore")
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

#state
class ChatState(TypedDict):
  thread_id:str
  recent_chats:List[str]
  relevant_chats:List[str]
  exit:bool
  latest_input:str
  tool_output:List[str]
  tool_query:List[str]
  pending_tool_call:List[dict]
  latest_response: str

#LLM
def groq_llm(tools=None):
    key = os.getenv("GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1"
    llm = ChatOpenAI(model="moonshotai/kimi-k2-instruct", temperature=0.1,api_key=key,base_url=url)
    if tools:
        return llm.bind_tools(tools)   # Bind tools so LLM can emit tool_call blocks
    return llm


#Tool
search_tool = DuckDuckGoSearchRun()
tools=[search_tool]
tool_map={tool.name:tool for tool in tools}
llm=groq_llm(tools=tools)


#Databases
checkpoint_db=sqlite3.connect("checkpoint.db",check_same_thread=False)
saver=SqliteSaver(checkpoint_db)

#sql db
convo_db=sqlite3.connect("conv0.db",check_same_thread=False)
convo_cursor=convo_db.cursor()
convo_cursor.execute(convo_db_creation_query)
convo_db.commit()

#embedding db
vectorstore=Chroma(
    embedding_function=HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2"
),
    persist_directory="vectorstore"
)

#To save the chats in db
def save_conversation(thread_id:str,role:str,message:str):
    ts=time.time()
    convo_cursor.execute(convo_insertion_query,(thread_id,role,message,ts)
    )
    convo_db.commit()

    convo_cursor.execute(convo_cleanup_query, (thread_id, thread_id))
    convo_db.commit()

    vectorstore.add_texts(
        texts=[message],
        metadatas=[{'role':role,'thread_id':thread_id,'timestamp':ts}]
    )

if __name__=="__main__":
    print(search_tool.invoke("ICC T20 World Cup 2026 final winner champion"))