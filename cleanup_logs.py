#!/usr/bin/env python3
"""
Utility script to clean up old log files, keeping only the latest N logs per type.
"""

import os
import glob
import argparse
from datetime import datetime

# Base directory for logs
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

def cleanup_logs(log_type, max_logs=5, dry_run=False):
    """
    Cleanup old log files, keeping only the latest N logs
    
    Args:
        log_type (str): Type of log ('api', 'tws', 'server', 'general', or 'all')
        max_logs (int): Number of log files to keep (default: 5)
        dry_run (bool): If True, only show what would be deleted without actually deleting
    """
    if log_type == 'all':
        log_types = ['api', 'tws', 'server', 'general']
    else:
        log_types = [log_type]
    
    total_removed = 0
    
    for lt in log_types:
        log_dir = os.path.join(LOGS_DIR, lt)
        if not os.path.exists(log_dir):
            print(f"Log directory not found: {log_dir}")
            continue
            
        log_pattern = os.path.join(log_dir, f"{lt}_*.log")
        
        # Get all log files for this type
        log_files = glob.glob(log_pattern)
        
        if not log_files:
            print(f"No log files found for type: {lt}")
            continue
            
        print(f"Found {len(log_files)} log files for type {lt}")
        
        # If we have more logs than the maximum, remove the oldest ones
        if len(log_files) > max_logs:
            # Sort by modification time (newest first)
            log_files.sort(key=os.path.getmtime, reverse=True)
            
            # Keep the newest max_logs
            to_keep = log_files[:max_logs]
            to_remove = log_files[max_logs:]
            
            print(f"Keeping {len(to_keep)} newest logs for {lt}:")
            for log in to_keep:
                mtime = os.path.getmtime(log)
                print(f"  - {os.path.basename(log)} (modified: {datetime.fromtimestamp(mtime)})")
            
            print(f"Removing {len(to_remove)} oldest logs for {lt}:")
            for old_log in to_remove:
                mtime = os.path.getmtime(old_log)
                print(f"  - {os.path.basename(old_log)} (modified: {datetime.fromtimestamp(mtime)})")
                
                if not dry_run:
                    try:
                        os.remove(old_log)
                        total_removed += 1
                    except Exception as e:
                        print(f"Error removing log file {old_log}: {e}")
        else:
            print(f"Only {len(log_files)} logs found for {lt}, all within the limit of {max_logs}.")
    
    if dry_run:
        print(f"Dry run completed. Would have removed {total_removed} log files.")
    else:
        print(f"Cleanup completed. Removed {total_removed} log files.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up old log files")
    parser.add_argument("--type", "-t", choices=["api", "tws", "server", "general", "all"], 
                        default="all", help="Type of logs to clean up (default: all)")
    parser.add_argument("--max", "-m", type=int, default=5,
                        help="Maximum number of log files to keep (default: 5)")
    parser.add_argument("--dry-run", "-d", action="store_true", 
                        help="Dry run mode - show what would be deleted without actually deleting")
    
    args = parser.parse_args()
    cleanup_logs(args.type, args.max, args.dry_run) 