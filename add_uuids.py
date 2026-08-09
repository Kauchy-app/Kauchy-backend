import os
import re

uuid_field = "    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)"

for root, dirs, files in os.walk('.'):
    if 'venv' in root or '.git' in root or 'migrations' in root or '.venv' in root:
        continue
    for file in files:
        if file == 'models.py':
            path = os.path.join(root, file)
            with open(path, 'r') as f:
                content = f.read()

            lines = content.split('\n')
            
            # Check if import uuid exists
            has_import = any('import uuid' in line for line in lines)
            if not has_import:
                # insert import uuid after the first import
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        lines.insert(i, 'import uuid')
                        break
                        
            final_lines = []
            
            i = 0
            while i < len(lines):
                line = lines[i]
                
                # Check for class definition
                m = re.match(r'^class (\w+)\((.*?)\):', line)
                if m:
                    base_classes = m.group(2)
                    # We only care about models.Model or AbstractUser or similar
                    # Actually, any class in models.py is likely a model.
                    if 'Model' in base_classes or 'AbstractUser' in base_classes:
                        final_lines.append(line)
                        
                        # Look ahead to see if 'id = ' is defined in this class before the next class
                        has_id = False
                        j = i + 1
                        while j < len(lines):
                            if re.match(r'^class \w+\(', lines[j]):
                                break
                            if re.match(r'^\s+id\s*=', lines[j]):
                                has_id = True
                                break
                            j += 1
                            
                        if not has_id:
                            final_lines.append(uuid_field)
                        
                        i += 1
                        continue
                        
                # Modify existing id = models.CharField(...) to UUIDField
                if re.match(r'^\s+id\s*=\s*models\.CharField\(primary_key=True', line):
                    final_lines.append(uuid_field)
                else:
                    final_lines.append(line)
                    
                i += 1

            with open(path, 'w') as f:
                f.write('\n'.join(final_lines))
                print(f"Processed {path}")
