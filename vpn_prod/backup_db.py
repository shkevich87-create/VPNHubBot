import os
import shutil
from datetime import datetime

source_db = 'instance/database.db'

backup_dir = 'instance/backup'

if not os.path.exists(backup_dir):
    os.makedirs(backup_dir)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_db = os.path.join(backup_dir, f'database-{timestamp}.db')

shutil.copy2(source_db, backup_db)

print(f'Резервная копия создана: {backup_db}')