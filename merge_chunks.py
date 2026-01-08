#!/usr/bin/env python3
"""
Merge chunked Augment conversation exports into single file for import.

Usage:
    python3 merge_chunks.py "Accessibility Upgrade for Login Controls_2026-01-05T22-59-10"
    
This will find all chunks matching the pattern and merge them into a single JSON file.
"""

import json
import sys
import glob
from pathlib import Path


def merge_chunks(base_name):
    """
    Merge chunked conversation export files.
    
    Args:
        base_name: Base filename without _chunk_XX suffix
                  Example: "Accessibility Upgrade for Login Controls_2026-01-05T22-59-10"
    """
    print(f"🔍 Finding chunks for: {base_name}")
    
    # Find all chunk files
    metadata_file = f"{base_name}_chunk_00_metadata.json"
    toolstates_file = f"{base_name}_chunk_01_toolstates.json"
    message_chunks = sorted(glob.glob(f"{base_name}_chunk_*_messages_*.json"))
    
    if not Path(metadata_file).exists():
        print(f"❌ Metadata file not found: {metadata_file}")
        return None
    
    print(f"📖 Reading metadata from {metadata_file}")
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    # Extract conversation info
    conversation = metadata.get('conversation', {})
    
    # Read tool states if exists
    tool_states = []
    if Path(toolstates_file).exists():
        print(f"📖 Reading tool states from {toolstates_file}")
        with open(toolstates_file, 'r') as f:
            toolstates_data = json.load(f)
            tool_states = toolstates_data.get('toolUseStates', [])
        print(f"   Found {len(tool_states)} tool states")
    
    # Read all message chunks
    chat_history = []
    print(f"📖 Reading {len(message_chunks)} message chunks...")
    for chunk_file in message_chunks:
        with open(chunk_file, 'r') as f:
            chunk_data = json.load(f)
            messages = chunk_data.get('chatHistory', [])
            chat_history.extend(messages)
            print(f"   {Path(chunk_file).name}: {len(messages)} messages")
    
    print(f"✅ Total messages: {len(chat_history)}")
    
    # Create merged conversation in format expected by conversation_manager.py
    # Format must match Augment export structure with nested "conversation" object
    merged = {
        "version": metadata.get('version', '1.0.0'),
        "exportedAt": metadata.get('exportedAt'),
        "conversation": {
            "id": conversation.get('id', base_name),
            "name": conversation.get('name', base_name),
            "createdAtIso": conversation.get('createdAtIso'),
            "lastInteractedAtIso": conversation.get('lastInteractedAtIso'),
            "isPinned": conversation.get('isPinned', False),
            "isShareable": conversation.get('isShareable', True),
            "personaType": conversation.get('personaType', 0),
            "draftActiveContextIds": conversation.get('draftActiveContextIds', []),
            "extraData": conversation.get('extraData', {}),
            "chatHistory": chat_history,
            "toolUseStates": tool_states
        }
    }
    
    # Write merged file
    output_file = f"{base_name}_merged.json"
    print(f"💾 Writing merged file: {output_file}")
    with open(output_file, 'w') as f:
        json.dump(merged, f, indent=2)

    # Get file size
    file_size_mb = Path(output_file).stat().st_size / (1024 * 1024)
    print(f"✅ Merged file created: {output_file} ({file_size_mb:.2f} MB)")
    print(f"📊 Summary:")
    print(f"   Conversation ID: {merged['conversation']['id']}")
    print(f"   Name: {merged['conversation']['name']}")
    print(f"   Messages: {len(chat_history)}")
    print(f"   Tool states: {len(tool_states)}")
    print(f"   File size: {file_size_mb:.2f} MB")
    
    return output_file


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 merge_chunks.py <base_filename>")
        print("\nExample:")
        print("  python3 merge_chunks.py 'Accessibility Upgrade for Login Controls_2026-01-05T22-59-10'")
        print("\nThis will merge all chunks:")
        print("  *_chunk_00_metadata.json")
        print("  *_chunk_01_toolstates.json")
        print("  *_chunk_XX_messages_*.json")
        print("\nInto a single file: <base_filename>_merged.json")
        sys.exit(1)
    
    base_name = sys.argv[1]
    
    # Remove _merged.json suffix if present
    if base_name.endswith('_merged.json'):
        base_name = base_name[:-12]
    
    # Remove .json suffix if present
    if base_name.endswith('.json'):
        base_name = base_name[:-5]
    
    output_file = merge_chunks(base_name)
    
    if output_file:
        print(f"\n🚀 Next step:")
        print(f"   python3 conversation_manager.py import \"{output_file}\"")


if __name__ == '__main__':
    main()

