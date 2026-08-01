from database.db_manager import get_db_manager
from database.models import Race

db = get_db_manager()
session = db.get_session()

# レース数を確認
races = session.query(Race).all()
print(f"総レース数: {len(races)}")

# レース番号ごとの件数
race_numbers = session.query(Race.race_number).distinct().all()
print(f"レース番号: {sorted([r[0] for r in race_numbers])}")

# 会場ごとのレース数
venues = session.query(Race.venue).distinct().all()
print(f"会場数: {len(venues)}")

# 会場ごとのレース数を詳細表示
from sqlalchemy import func
venue_race_counts = session.query(Race.venue, func.count(Race.race_number)).group_by(Race.venue).all()
print(f"\n会場ごとのレース数:")
for venue, count in sorted(venue_race_counts):
    print(f"  {venue}: {count}レース")

session.close()
