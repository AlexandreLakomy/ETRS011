PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE DonneeEquipement ( 
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipement_id INTEGER NOT NULL,
    oid_id INTEGER NOT NULL,
    valeur REAL NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipement_id) REFERENCES Equipement (id) ON DELETE CASCADE,
    FOREIGN KEY (oid_id) REFERENCES OID (id) ON DELETE CASCADE
);
CREATE TABLE Equipement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    ip TEXT NOT NULL UNIQUE,
    type TEXT,
    community TEXT DEFAULT 'public',
    intervalle INTEGER DEFAULT 60  -- secondes entre deux collectes
);
CREATE TABLE OID (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifiant TEXT NOT NULL,
    nomParametre TEXT NOT NULL,
    typeValeur TEXT NOT NULL,  -- Float, Integer, String
    equipement_id INTEGER NOT NULL,
    seuilMax REAL,             -- optionnel
    seuilMin REAL,             -- optionnel
    alerte_active BOOLEAN DEFAULT 0,
    FOREIGN KEY (equipement_id) REFERENCES Equipement (id) ON DELETE CASCADE
);
CREATE TABLE Seuil (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    oid_id INTEGER NOT NULL,
    valeurMax REAL,
    valeurMin REAL,
    niveauAlerte TEXT CHECK(niveauAlerte IN ('alerte', 'critique')),
    FOREIGN KEY (oid_id) REFERENCES OID (id) ON DELETE CASCADE
);
CREATE TABLE Utilisateur (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    mot_de_passe TEXT NOT NULL,
    date_creation DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_admin BOOLEAN DEFAULT 0
);
COMMIT;
