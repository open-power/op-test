#!/usr/bin/env python3
"""
Op-Test SSH Migration Script
-----------------------------

This script helps automate the migration of test cases from pexpect-based
console operations to the new SSH-based architecture.

Usage:
    python3 migrate_to_ssh.py <test_file.py>
    python3 migrate_to_ssh.py --all  # Migrate all test files
    python3 migrate_to_ssh.py --check <test_file.py>  # Check only, no changes
"""

import sys
import os
import re
import argparse
from pathlib import Path


class SSHMigrationTool:
    """Tool to migrate test cases to new SSH architecture"""
    
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.changes_made = []
        
    def migrate_file(self, filepath):
        """Migrate a single test file"""
        # Convert to string if Path object
        filepath = str(filepath)
        
        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Migrating: {filepath}")
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Apply migrations
        content = self.remove_pexpect_imports(content)
        content = self.add_ssh_imports(content)
        content = self.migrate_console_operations(content)
        content = self.migrate_sendline_expect(content)
        content = self.migrate_error_handling(content)
        
        if content != original_content:
            if not self.dry_run:
                # Backup original file
                backup_path = filepath + '.backup'
                with open(backup_path, 'w') as f:
                    f.write(original_content)
                print(f"  Backup created: {backup_path}")
                
                # Write migrated content
                with open(filepath, 'w') as f:
                    f.write(content)
                print(f"  ✓ File migrated successfully")
            else:
                print(f"  Would migrate file (dry run)")
            
            self.print_changes()
            return True
        else:
            print(f"  No changes needed")
            return False
    
    def remove_pexpect_imports(self, content):
        """Remove pexpect imports"""
        patterns = [
            r'import pexpect\n',
            r'from pexpect import .*\n',
        ]
        
        for pattern in patterns:
            if re.search(pattern, content):
                self.changes_made.append(f"Removed pexpect import")
                content = re.sub(pattern, '', content)
        
        return content
    
    def add_ssh_imports(self, content):
        """Add new SSH imports if not present"""
        ssh_imports = """from common.OpTestSSHConnection import OpTestSSHConnection, OpTestCommandResult
from common.OpTestCommandExecutor import OpTestCommandExecutor
from common.Exceptions import SSHCommandFailed, SSHSessionDisconnected
"""
        
        # Check if imports already exist
        if 'OpTestSSHConnection' not in content:
            # Find where to insert (after other imports)
            import_section = re.search(r'(import .*\n)+', content)
            if import_section:
                insert_pos = import_section.end()
                content = content[:insert_pos] + '\n' + ssh_imports + content[insert_pos:]
                self.changes_made.append("Added new SSH imports")
        
        return content
    
    def migrate_console_operations(self, content):
        """Migrate console.get_console() to direct SSH"""
        patterns = [
            # Pattern: c = self.cv_SYSTEM.console.get_console()
            (r'(\s+)c = self\.cv_SYSTEM\.console\.get_console\(\)',
             r'\1# Using new SSH architecture - no console needed'),
            
            # Pattern: self.cv_SYSTEM.console.run_command(...)
            (r'self\.cv_SYSTEM\.console\.run_command\(([^)]+)\)',
             r'self.cv_HOST.host_run_command(\1)'),
        ]
        
        for pattern, replacement in patterns:
            if re.search(pattern, content):
                self.changes_made.append(f"Migrated console operation")
                content = re.sub(pattern, replacement, content)
        
        return content
    
    def migrate_sendline_expect(self, content):
        """Migrate sendline/expect patterns to direct commands"""
        # Pattern: c.sendline("command")
        #          c.expect(prompt)
        #          output = c.before
        
        pattern = r'(\s+)c\.sendline\(["\']([^"\']+)["\']\)\s*\n\s+c\.expect\([^)]+\)\s*\n\s+(\w+) = c\.before'
        
        def replace_func(match):
            indent = match.group(1)
            command = match.group(2)
            var_name = match.group(3)
            self.changes_made.append(f"Migrated sendline/expect pattern for: {command}")
            return f'{indent}result = self.cv_HOST.host_run_command("{command}")\n{indent}{var_name} = \'\\n\'.join(result)'
        
        content = re.sub(pattern, replace_func, content)
        
        return content
    
    def migrate_error_handling(self, content):
        """Migrate pexpect error handling to SSH exceptions"""
        patterns = [
            # pexpect.TIMEOUT -> SSHCommandFailed
            (r'except pexpect\.TIMEOUT:',
             r'except SSHCommandFailed as e:'),
            
            # pexpect.EOF -> SSHSessionDisconnected
            (r'except pexpect\.EOF:',
             r'except SSHSessionDisconnected as e:'),
        ]
        
        for pattern, replacement in patterns:
            if re.search(pattern, content):
                self.changes_made.append(f"Migrated error handling")
                content = re.sub(pattern, replacement, content)
        
        return content
    
    def print_changes(self):
        """Print summary of changes made"""
        if self.changes_made:
            print("\n  Changes made:")
            for change in self.changes_made:
                print(f"    - {change}")
            self.changes_made = []


def find_test_files(directory='testcases'):
    """Find all Python test files"""
    test_dir = Path(directory)
    if not test_dir.exists():
        print(f"Error: Directory {directory} not found")
        return []
    
    return list(test_dir.glob('*.py'))


def main():
    parser = argparse.ArgumentParser(
        description='Migrate op-test test cases to new SSH architecture'
    )
    parser.add_argument('files', nargs='*', help='Test files to migrate')
    parser.add_argument('--all', action='store_true', 
                       help='Migrate all test files in testcases/')
    parser.add_argument('--check', action='store_true',
                       help='Check only, do not modify files (dry run)')
    parser.add_argument('--testcases-dir', default='testcases',
                       help='Directory containing test cases (default: testcases)')
    
    args = parser.parse_args()
    
    # Determine files to migrate
    if args.all:
        files = find_test_files(args.testcases_dir)
        if not files:
            print("No test files found")
            return 1
    elif args.files:
        files = [Path(f) for f in args.files]
    else:
        parser.print_help()
        return 1
    
    # Create migration tool
    tool = SSHMigrationTool(dry_run=args.check)
    
    # Migrate files
    print(f"\n{'='*60}")
    print(f"Op-Test SSH Migration Tool")
    print(f"{'='*60}")
    print(f"Mode: {'DRY RUN (no changes)' if args.check else 'MIGRATION (will modify files)'}")
    print(f"Files to process: {len(files)}")
    
    migrated_count = 0
    for filepath in files:
        if not filepath.exists():
            print(f"\nWarning: File not found: {filepath}")
            continue
        
        if tool.migrate_file(filepath):
            migrated_count += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Migration Summary")
    print(f"{'='*60}")
    print(f"Files processed: {len(files)}")
    print(f"Files {'would be ' if args.check else ''}migrated: {migrated_count}")
    print(f"Files unchanged: {len(files) - migrated_count}")
    
    if args.check and migrated_count > 0:
        print(f"\nRun without --check to apply changes")
    elif not args.check and migrated_count > 0:
        print(f"\nBackup files created with .backup extension")
        print(f"Review changes and test before committing")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

# Made with Bob
