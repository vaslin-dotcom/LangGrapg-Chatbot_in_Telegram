from langgraph.graph import StateGraph,END
from langchain_core.messages import HumanMessage,SystemMessage
from prompts import chat_prompt
from queries import chat_retrieval_query
from schemas import *
from datetime import datetime

#Human node for user input
def human_node(state:ChatState):
  #print('------------------------------------------------------------------------------------')
  user_input=state['latest_input']
  if 'exit' in user_input.lower():
    return{**state,'exit':True,'latest_input':user_input}
  save_conversation(state['thread_id'],'human',user_input)
  return {**state,'latest_input':user_input,'pending_tool_call':[]}

#process node for retrieving recent and relevant chats
def process_node(state:ChatState):
  thread_id=state['thread_id']

  convo_cursor.execute(chat_retrieval_query, (thread_id,))
  rows=convo_cursor.fetchall()
  recent_chats=[f"{role}:{message}" for role,message in rows ]

  #recent_context = "\n".join(recent_chats)
  result = vectorstore.similarity_search(
      state['latest_input'] ,
      k=10,
      filter={'thread_id': thread_id}
  )

  relevant_chats=[doc.page_content for doc in result ]

  return {
      **state,
      'recent_chats':recent_chats,
      'relevant_chats':relevant_chats
  }

#chat node AI response
def chat_node(state:ChatState):
  tool_context=''
  if state.get('tool_output'):
    pairs=zip(state.get('tool_query',[]),state.get('tool_output'))
    tool_context='\n'.join([f"{query}:{output}" for query,output in pairs])

  system_prompt = chat_prompt.format(
    relevant="\n".join(state["relevant_chats"]) or "None",
    recent="\n".join(state["recent_chats"]) or "None",
    tool_context=tool_context,
    current_date=datetime.now().strftime("%B %d, %Y")
)
  messages=[SystemMessage(content=system_prompt),
            HumanMessage(content=state['latest_input'])]

  response=llm.invoke(messages)

  if response.tool_calls:
    return {
        **state,'pending_tool_call':response.tool_calls
    }

  #print('------------------------------------------------------------------------------------')
  #print("Assistant:",response.content)
  save_conversation(state['thread_id'],'assistant',response.content)

  return{
      **state,
      'recent_chats':[],
      'latest_response': response.content,
      'relevant_chats':[],
      'tool_output':[],
      'tool_query':[],
      'pending_tool_call':[]
  }

#Tool node invoking tools
def tool_node(state:ChatState):
  pendings=state['pending_tool_call']
  outputs=[]
  tool_queries=[]
  for pending in pendings:
    tool_name=pending['name']
    tool_args=pending['args']
    tool_queries.append(tool_args)
    tool=tool_map.get(tool_name)

    if tool:
      try:
        if isinstance(tool_args, dict) and len(tool_args) == 1:
            result = tool.run(next(iter(tool_args.values())))
        elif isinstance(tool_args, dict):
            result = tool.run(tool_args)
        else:
            result = tool.run(str(tool_args))
        outputs.append(str(result))
      except Exception as e:
        outputs.append(f"[Tool error {e}]")
    else:
      outputs.append(f"[Unknown tool {tool_name}]")
  return{
        **state,
        'pending_tool_call':[],
        'tool_output':outputs,
        'tool_query':tool_queries
    }

#condition for conditional edges
# def condition(state:ChatState):
#   if state['exit']:
#     return END
#   if state.get('pending_tool_call'):
#     return 'tool'
#   return 'human'

def condition(state: ChatState):
    if state.get('pending_tool_call'):
        return 'tool'
    return END                                  # CHANGED: was returning 'human' to loop — now always ENDs




graph=StateGraph(ChatState)
graph.add_node('human',human_node)
graph.add_node('process',process_node)
graph.add_node('chat',chat_node)
graph.add_node('tool',tool_node)
graph.set_entry_point('human')
graph.add_edge('human','process')
graph.add_edge('process','chat')
graph.add_edge('tool','chat')
graph.add_conditional_edges('chat',condition,{
    END:END,
    'tool':'tool'
})

app=graph.compile(checkpointer=saver)