import json
import os
from typing import List, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Product, create_tables, drop_tables
from app.core.config import BusinessType, settings


class DatabaseSeeder:
    """Utility class to seed database with sample data"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(
            self.database_url,
            connect_args={"check_same_thread": False} if "sqlite" in self.database_url else {}
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def seed_all_business_types(self, reset: bool = False):
        """Seed data for all business types"""
        if reset:
            drop_tables(self.engine)
        
        create_tables(self.engine)
        
        # Seed each business type
        for business_type in BusinessType:
            if business_type != BusinessType.GENERIC:
                self.seed_business_type(business_type)
    
    def seed_business_type(self, business_type: BusinessType):
        """Seed data for a specific business type"""
        seed_file = self._get_seed_file(business_type)
        
        if not os.path.exists(seed_file):
            print(f"Seed file not found: {seed_file}")
            return
        
        with open(seed_file, 'r') as f:
            data = json.load(f)
        
        db = self.SessionLocal()
        try:
            for item_data in data:
                # Check if product already exists
                existing = db.query(Product).filter(
                    Product.id == item_data['id']
                ).first()
                
                if existing:
                    print(f"Product {item_data['id']} already exists, skipping...")
                    continue
                
                product = Product.from_dict(item_data, business_type)
                db.add(product)
            
            db.commit()
            print(f"Successfully seeded {len(data)} products for {business_type.value}")
            
        except Exception as e:
            db.rollback()
            print(f"Error seeding {business_type.value}: {str(e)}")
        finally:
            db.close()
    
    def _get_seed_file(self, business_type: BusinessType) -> str:
        """Get the seed file path for a business type"""
        seed_files = {
            BusinessType.ECOMMERCE: "app/data/seeds/ecommerce_products.json",
            BusinessType.HOTEL: "app/data/seeds/hotel_rooms.json",
            BusinessType.REAL_ESTATE: "app/data/seeds/real_estate_properties.json",
            BusinessType.RENTAL: "app/data/seeds/rental_items.json"
        }
        
        return seed_files.get(business_type, "")
    
    def clear_all_data(self):
        """Clear all data from database"""
        db = self.SessionLocal()
        try:
            db.query(Product).delete()
            db.commit()
            print("All data cleared from database")
        except Exception as e:
            db.rollback()
            print(f"Error clearing data: {str(e)}")
        finally:
            db.close()


# CLI utility
if __name__ == "__main__":
    import sys
    
    seeder = DatabaseSeeder()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "seed":
            seeder.seed_all_business_types(reset=True)
        elif command == "clear":
            seeder.clear_all_data()
        else:
            print("Usage: python seed_database.py [seed|clear]")
    else:
        seeder.seed_all_business_types(reset=True) 