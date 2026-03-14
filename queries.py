chat_retrieval_query="""
    SELECT role, message FROM (
        SELECT role, message, timestamp
        FROM conversations
        WHERE thread_id=?
        ORDER BY timestamp DESC
        LIMIT 10
    ) ORDER BY timestamp ASC  -- ✅ oldest first, natural flow
"""

convo_db_creation_query="""
    create table if not exists conversations(
        id integer primary key autoincrement,
        thread_id text ,
        role text,
        message text,
        timestamp real
    )
"""

convo_insertion_query="""
        insert into conversations(thread_id,role,message,timestamp)
        values(?,?,?,?)
    """

convo_cleanup_query = """
    DELETE FROM conversations
    WHERE thread_id = ?
    AND id NOT IN (
        SELECT id FROM conversations
        WHERE thread_id = ?
        ORDER BY timestamp DESC
        LIMIT 20
    )
"""