#!/usr/bin/env python3
"""Simple database viewer for development."""
import sqlite3
import json
from datetime import datetime

DB_PATH = "database.db"

def view_recent_itineraries(limit=10):
    """Show recent sectioned itineraries."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, destination, title, created_at, updated_at
        FROM sectioned_itinerary
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    print(f"\n{'='*80}")
    print(f"RECENT ITINERARIES (last {limit})")
    print(f"{'='*80}\n")

    for row in cursor.fetchall():
        id_, dest, title, created, updated = row
        print(f"ID: {id_}")
        print(f"Destination: {dest}")
        print(f"Title: {title}")
        print(f"Created: {created}")
        print(f"Updated: {updated}")
        print("-" * 80)

    conn.close()

def view_itinerary_details(itinerary_id):
    """Show full details of an itinerary."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT destination, title, sections_json, created_at
        FROM sectioned_itinerary
        WHERE id = ?
    """, (itinerary_id,))

    row = cursor.fetchone()
    if not row:
        print(f"Itinerary {itinerary_id} not found")
        return

    dest, title, sections_json, created = row
    sections = json.loads(sections_json)

    print(f"\n{'='*80}")
    print(f"{title} - {dest}")
    print(f"Created: {created}")
    print(f"{'='*80}\n")

    # Show activities
    if 'activities' in sections and 'days' in sections['activities']:
        days = sections['activities']['days']
        print(f"Activities: {len(days)} days")
        for day in days:
            activities = day.get('activities', [])
            print(f"  Day {day.get('day_number')}: {day.get('title')} - {len(activities)} activities")

    # Show logistics
    if 'logistics' in sections:
        logistics = sections['logistics']
        print(f"\nLogistics:")
        for key in ['transportation', 'packing', 'visa_requirements', 'health_safety']:
            if key in logistics:
                print(f"  ✓ {key.replace('_', ' ').title()}")

    conn.close()

def watch_mode():
    """Watch for new itineraries (simple polling)."""
    import time
    print("\n🔍 Watching for new itineraries... (Ctrl+C to stop)\n")

    last_count = 0
    while True:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sectioned_itinerary")
        count = cursor.fetchone()[0]
        conn.close()

        if count > last_count:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] New itinerary created! Total: {count}")
            last_count = count

        time.sleep(2)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "watch":
            watch_mode()
        else:
            view_itinerary_details(sys.argv[1])
    else:
        view_recent_itineraries()
