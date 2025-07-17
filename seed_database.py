#!/usr/bin/env python3
"""
Database seeding script for the e-commerce agent system.
Creates tables and populates with sample product data.
"""

import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, Product
from app.core.config import BusinessType


def create_database():
    """Create database tables"""
    engine = create_engine("sqlite:///products.db")
    Base.metadata.create_all(engine)
    return engine


def seed_products(engine):
    """Seed database with sample products"""
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Clear existing data
        session.query(Product).delete()
        session.commit()
        
        # Sample laptop products
        laptop_products = [
            {
                "id": "lap_dell_xps13",
                "name": "Dell XPS 13",
                "description": "13.3-inch ultrabook with Intel Core i7, 16GB RAM, 512GB SSD. Perfect for professionals.",
                "price": 899.99,
                "category": "laptops",
                "product_metadata": {
                    "color": "silver",
                    "brand": "Dell",
                    "processor": "Intel Core i7",
                    "ram": "16GB",
                    "storage": "512GB SSD",
                    "screen_size": "13.3 inches",
                    "os": "Windows 11"
                },
                "availability": True,
                "image_url": "https://images.example.com/dell-xps-13.jpg",
                "business_type": BusinessType.ECOMMERCE.value
            },
            {
                "id": "lap_macbook_air",
                "name": "MacBook Air M2",
                "description": "Apple's latest MacBook Air with M2 chip, 8GB RAM, 256GB SSD. Lightweight and powerful.",
                "price": 999.99,
                "category": "laptops",
                "product_metadata": {
                    "color": "silver",
                    "brand": "Apple",
                    "processor": "Apple M2",
                    "ram": "8GB",
                    "storage": "256GB SSD",
                    "screen_size": "13.6 inches",
                    "os": "macOS"
                },
                "availability": True,
                "image_url": "https://images.example.com/macbook-air-m2.jpg",
                "business_type": BusinessType.ECOMMERCE.value
            },
            {
                "id": "lap_lenovo_thinkpad",
                "name": "Lenovo ThinkPad X1 Carbon",
                "description": "Business laptop with Intel Core i5, 16GB RAM, 512GB SSD. Durable and reliable.",
                "price": 849.99,
                "category": "laptops",
                "product_metadata": {
                    "color": "black",
                    "brand": "Lenovo",
                    "processor": "Intel Core i5",
                    "ram": "16GB",
                    "storage": "512GB SSD",
                    "screen_size": "14 inches",
                    "os": "Windows 11"
                },
                "availability": True,
                "image_url": "https://images.example.com/thinkpad-x1.jpg",
                "business_type": BusinessType.ECOMMERCE.value
            },
            {
                "id": "lap_hp_pavilion",
                "name": "HP Pavilion 15",
                "description": "Budget-friendly laptop with AMD Ryzen 5, 8GB RAM, 256GB SSD. Great for students.",
                "price": 649.99,
                "category": "laptops",
                "product_metadata": {
                    "color": "silver",
                    "brand": "HP",
                    "processor": "AMD Ryzen 5",
                    "ram": "8GB",
                    "storage": "256GB SSD",
                    "screen_size": "15.6 inches",
                    "os": "Windows 11"
                },
                "availability": True,
                "image_url": "https://images.example.com/hp-pavilion.jpg",
                "business_type": BusinessType.ECOMMERCE.value
            },
            {
                "id": "lap_asus_vivobook",
                "name": "ASUS VivoBook 14",
                "description": "Compact laptop with Intel Core i3, 8GB RAM, 256GB SSD. Portable and affordable.",
                "price": 549.99,
                "category": "laptops",
                "product_metadata": {
                    "color": "blue",
                    "brand": "ASUS",
                    "processor": "Intel Core i3",
                    "ram": "8GB",
                    "storage": "256GB SSD",
                    "screen_size": "14 inches",
                    "os": "Windows 11"
                },
                "availability": True,
                "image_url": "https://images.example.com/asus-vivobook.jpg",
                "business_type": BusinessType.ECOMMERCE.value
            },
            {
                "id": "lap_acer_aspire",
                "name": "Acer Aspire 5",
                "description": "Mid-range laptop with AMD Ryzen 7, 12GB RAM, 512GB SSD. Excellent performance.",
                "price": 749.99,
                "category": "laptops",
                "product_metadata": {
                    "color": "silver",
                    "brand": "Acer",
                    "processor": "AMD Ryzen 7",
                    "ram": "12GB",
                    "storage": "512GB SSD",
                    "screen_size": "15.6 inches",
                    "os": "Windows 11"
                },
                "availability": True,
                "image_url": "https://images.example.com/acer-aspire.jpg",
                "business_type": BusinessType.ECOMMERCE.value
            },
            {
                "id": "lap_msi_gaming",
                "name": "MSI Gaming Laptop GF63",
                "description": "Gaming laptop with Intel Core i7, 16GB RAM, 1TB SSD, NVIDIA GTX 1650. High performance.",
                "price": 1199.99,
                "category": "laptops",
                "product_metadata": {
                    "color": "black",
                    "brand": "MSI",
                    "processor": "Intel Core i7",
                    "ram": "16GB",
                    "storage": "1TB SSD",
                    "screen_size": "15.6 inches",
                    "os": "Windows 11",
                    "gpu": "NVIDIA GTX 1650"
                },
                "availability": False,  # Out of stock
                "image_url": "https://images.example.com/msi-gaming.jpg",
                "business_type": BusinessType.ECOMMERCE.value
            },
            {
                "id": "lap_surface_laptop",
                "name": "Microsoft Surface Laptop 5",
                "description": "Premium laptop with Intel Core i5, 8GB RAM, 256GB SSD. Elegant design.",
                "price": 999.99,
                "category": "laptops",
                "product_metadata": {
                    "color": "platinum",
                    "brand": "Microsoft",
                    "processor": "Intel Core i5",
                    "ram": "8GB",
                    "storage": "256GB SSD",
                    "screen_size": "13.5 inches",
                    "os": "Windows 11"
                },
                "availability": True,
                "image_url": "https://images.example.com/surface-laptop.jpg",
                "business_type": BusinessType.ECOMMERCE.value
            }
        ]
        
        # Add some non-laptop products for variety
        other_products = [
            {
                "id": "phone_iphone15",
                "name": "iPhone 15",
                "description": "Latest iPhone with A17 Pro chip, 128GB storage, 48MP camera.",
                "price": 799.99,
                "category": "phones",
                "product_metadata": {
                    "color": "blue",
                    "brand": "Apple",
                    "storage": "128GB",
                    "camera": "48MP"
                },
                "availability": True,
                "image_url": "https://images.example.com/iphone-15.jpg",
                "business_type": BusinessType.ECOMMERCE.value
            },
            {
                "id": "tablet_ipad_air",
                "name": "iPad Air",
                "description": "Versatile tablet with M1 chip, 64GB storage, 10.9-inch display.",
                "price": 599.99,
                "category": "tablets",
                "product_metadata": {
                    "color": "space_gray",
                    "brand": "Apple",
                    "storage": "64GB",
                    "screen_size": "10.9 inches"
                },
                "availability": True,
                "image_url": "https://images.example.com/ipad-air.jpg",
                "business_type": BusinessType.ECOMMERCE.value
            }
        ]
        
        all_products = laptop_products + other_products
        
        # Insert products
        for product_data in all_products:
            product = Product(**product_data)
            session.add(product)
        
        session.commit()
        print(f"✅ Successfully seeded {len(all_products)} products")
        
        # Verify seeding
        laptop_count = session.query(Product).filter(Product.category == "laptops").count()
        total_count = session.query(Product).count()
        
        print(f"📊 Database stats:")
        print(f"   - Total products: {total_count}")
        print(f"   - Laptops: {laptop_count}")
        print(f"   - Products under $1000: {session.query(Product).filter(Product.price < 1000).count()}")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("🚀 Initializing database...")
    engine = create_database()
    print("✅ Database tables created")
    
    print("\n📦 Seeding products...")
    seed_products(engine)
    print("✅ Database seeding complete!") 