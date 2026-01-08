#!/usr/bin/env python3
"""Capture BEFORE state of trigger function"""
from conversation_manager import ConversationManager

cm = ConversationManager()
cursor = cm.pg_conn.cursor()

cursor.execute("""
    SELECT pg_get_functiondef(oid)
    FROM pg_proc
    WHERE proname = 'chat_history_search_vector_trigger'
""")
result = cursor.fetchone()

if result:
    print('BEFORE STATE: Trigger Function Definition')
    print('='*60)
    print(result[0])
    print('='*60)
else:
    print('Function not found')

cursor.close()

