from db import db

class Role(db.Model):
    __tablename__ = 'roles'
    name = db.Column(db.String(50), primary_key=True)
    description = db.Column(db.String(200), nullable=True)

    def __init__(self, name, description=None):
        self.name = name
        self.description = description

    @staticmethod
    def get_all_roles():
        """Retourne tous les rôles disponibles"""
        return [role.name for role in Role.query.all()]

    @staticmethod
    def initialize_roles():
        """Initialise les rôles par défaut dans la base de données"""
        default_roles = [
            'Team Bureau', 'Team Partenariat', 'Team Com', 'Team BDA', 'Team BDS',
            'Team Soirée', 'Team FISA', 'Team Opé', 'Team Argent', 'Team Logistique',
            'Team Orga', 'Team Animation', 'Team Sécu', 'Team Film', 'Team E-BDS',
            'Team Silencieuses', 'Team Standard', 'Team Goodies', 'Team INFO', 'Team A&C'
        ]

        for role_name in default_roles:
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name)
                db.session.add(role)

        db.session.commit()