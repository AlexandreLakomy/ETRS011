BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "Alerte" (
	"id"	INTEGER,
	"equipement_id"	INTEGER NOT NULL,
	"oid_id"	INTEGER NOT NULL,
	"valeurActuelle"	REAL NOT NULL,
	"timestamp"	DATETIME NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("equipement_id") REFERENCES "Equipement"("id"),
	FOREIGN KEY("oid_id") REFERENCES "OID"("id")
);
CREATE TABLE IF NOT EXISTS "ConfigurationManager" (
	"id"	INTEGER,
	"equipement_id"	INTEGER,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("equipement_id") REFERENCES "Equipement"("id")
);
CREATE TABLE IF NOT EXISTS "DonneesEquipement" (
	"id"	INTEGER,
	"moniteur_id"	INTEGER NOT NULL,
	"timestamp"	DATETIME NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("moniteur_id") REFERENCES "MoniteurSNMP"("id")
);
CREATE TABLE IF NOT EXISTS "DonneesValeurs" (
	"id"	INTEGER,
	"donneesEquipement_id"	INTEGER NOT NULL,
	"oid_id"	INTEGER NOT NULL,
	"valeur"	REAL NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("donneesEquipement_id") REFERENCES "DonneesEquipement"("id") ON DELETE CASCADE,
	FOREIGN KEY("oid_id") REFERENCES "OID"("id")
);
CREATE TABLE IF NOT EXISTS "Equipement" (
	"id"	INTEGER,
	"nom"	TEXT NOT NULL,
	"ip"	TEXT NOT NULL,
	"type"	TEXT NOT NULL,
	"modeleControle_id"	INTEGER,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("modeleControle_id") REFERENCES "ModeleControle"("id")
);
CREATE TABLE IF NOT EXISTS "InterfaceUtilisateur" (
	"id"	INTEGER,
	"moniteur_id"	INTEGER NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("moniteur_id") REFERENCES "MoniteurSNMP"("id")
);
CREATE TABLE IF NOT EXISTS "ModeleControle" (
	"id"	INTEGER,
	"nom"	TEXT NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "MoniteurSNMP" (
	"id"	INTEGER,
	"equipement_id"	INTEGER NOT NULL,
	"intervalle"	INTEGER NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("equipement_id") REFERENCES "Equipement"("id")
);
CREATE TABLE IF NOT EXISTS "OID" (
	"id"	INTEGER,
	"identifiant"	TEXT NOT NULL,
	"nomParametre"	TEXT NOT NULL,
	"typeValeur"	TEXT NOT NULL,
	"equipement_id"	INTEGER NOT NULL,
	"seuil_id"	INTEGER,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("equipement_id") REFERENCES "Equipement"("id"),
	FOREIGN KEY("seuil_id") REFERENCES "Seuil"("id")
);
CREATE TABLE IF NOT EXISTS "ParametreSurveille" (
	"id"	INTEGER,
	"nom"	TEXT NOT NULL,
	"typeValeur"	TEXT NOT NULL,
	"unite"	TEXT,
	"oid_id"	INTEGER,
	"seuil_id"	INTEGER,
	"modeleControle_id"	INTEGER NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("modeleControle_id") REFERENCES "ModeleControle"("id"),
	FOREIGN KEY("oid_id") REFERENCES "OID"("id"),
	FOREIGN KEY("seuil_id") REFERENCES "Seuil"("id")
);
CREATE TABLE IF NOT EXISTS "Seuil" (
	"id"	INTEGER,
	"nom"	TEXT NOT NULL,
	"valeurMax"	REAL NOT NULL,
	"valeurMin"	REAL,
	"niveauAlerte"	TEXT CHECK("niveauAlerte" IN ('alerte', 'alarme')),
	PRIMARY KEY("id" AUTOINCREMENT)
);
COMMIT;
