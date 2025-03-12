#!/usr/bin/env python3
"""
Utility script to view logs
"""

import os
import sys
import argparse
from datetime import datetime

LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

def list_log_files(log_type=None):
    """List all log files of a specific type or all types"""
    if log_type:
        log_dir = os.path.join(LOGS_DIR, log_type)
        if not os.path.exists(log_dir):
            print(f"No logs directory found for type: {log_type}")
            return []
        
        log_files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) 
                    if os.path.isfile(os.path.join(log_dir, f)) and f.endswith('.log')]
    else:
        log_files = []
        for root, _, files in os.walk(LOGS_DIR):
            for file in files:
                if file.endswith('.log'):
                    log_files.append(os.path.join(root, file))
    
    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return log_files

def display_log_file(log_file, tail=None):
    """Display contents of a log file, optionally only showing the last N lines"""
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return
    
    print(f"\n{'='*80}")
    print(f"Log file: {os.path.basename(log_file)}")
    print(f"Last modified: {datetime.fromtimestamp(os.path.getmtime(log_file))}")
    print(f"Size: {os.path.getsize(log_file)/1024:.2f} KB")
    print(f"{'='*80}\n")
    
    try:
        with open(log_file, 'r') as f:
            if tail:
                # Read the whole file but only keep the last N lines
                lines = f.readlines()
                if len(lines) > tail:
                    lines = lines[-tail:]
                for line in lines:
                    print(line.rstrip())
            else:
                # Just print the whole file
                print(f.read())
    except UnicodeDecodeError:
        print("Error reading log file - file may be corrupt or binary.")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='View Auto-Trader logs')
    parser.add_argument('--type', choices=['api', 'tws', 'server', 'general'],
                        help='Type of logs to view')
    parser.add_argument('--tail', type=int, default=50,
                        help='Number of lines to show from the end of each log (0 for all)')
    parser.add_argument('--list', action='store_true',
                        help='List log files only without showing contents')
    
    args = parser.parse_args()
    
    log_files = list_log_files(args.type)
    
    if not log_files:
        print("No log files found.")
        return
    
    if args.list:
        # Just list the log files
        print(f"Found {len(log_files)} log file(s):")
        for i, log_file in enumerate(log_files, 1):
            rel_path = os.path.relpath(log_file, LOGS_DIR)
            size_kb = os.path.getsize(log_file)/1024
            mod_time = datetime.fromtimestamp(os.path.getmtime(log_file))
            print(f"{i}. {rel_path:<40} {size_kb:>8.2f} KB  {mod_time}")
    else:
        # Display the most recent log file by default
        display_log_file(log_files[0], tail=args.tail if args.tail > 0 else None)

if __name__ == '__main__':
    main() 