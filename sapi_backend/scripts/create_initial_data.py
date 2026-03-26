from passlib.context import CryptContext
from app.db.session import SessionLocal
from app.db.models.user import User
from app.db.models.document import DocumentType
from app.core.security import get_password_hash


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_initial_data():
    db = SessionLocal()
    
    try:
        existing_admin = db.query(User).filter(User.username == "admin").first()
        if not existing_admin:
            admin_user = User(
                username="admin",
                email="admin@sapi.local",
                full_name="Administrator",
                hashed_password=get_password_hash("admin123"),
                role="admin",
                is_active=True,
                is_superuser=True
            )
            db.add(admin_user)
            print("Admin user created: admin / admin123")
        
        demo_user = db.query(User).filter(User.username == "demo").first()
        if not demo_user:
            user = User(
                username="demo",
                email="demo@sapi.local",
                full_name="Demo User",
                hashed_password=get_password_hash("demo123"),
                role="user",
                is_active=True,
                is_superuser=False
            )
            db.add(user)
            print("Demo user created: demo / demo123")
        
        doc_types = [
            ("Factura de Proveedor", "Documentos de facturas emitidas por proveedores"),
            ("Contrato Simple", "Documentos de contratos simples"),
        ]
        
        for name, description in doc_types:
            existing_type = db.query(DocumentType).filter(DocumentType.name == name).first()
            if not existing_type:
                doc_type = DocumentType(
                    name=name,
                    description=description,
                    is_active=True
                )
                db.add(doc_type)
                print(f"Document type created: {name}")
        
        db.commit()
        print("Initial data created successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating initial data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_initial_data()
