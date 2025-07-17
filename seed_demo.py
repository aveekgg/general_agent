#!/usr/bin/env python3
"""
Simple script to seed the database with demo data
"""

from app.data.seed_database import DatabaseSeeder

def main():
    print("🌱 Seeding database with demo data...")
    
    seeder = DatabaseSeeder()
    seeder.seed_all_business_types(reset=True)
    
    print("✅ Database seeding completed!")
    print("\nNow you can test:")
    print("- 'show me laptops within $1000' → Will return real results!")
    print("- 'red laptops' → Will filter by color!")
    print("- 'Dell laptops' → Will filter by brand!")

if __name__ == "__main__":
    main() 