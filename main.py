#!/usr/bin/env python3
"""
Google Drive Manager - Télécharger, lister et uploader des fichiers
Nécessite : pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
"""

import os
import io
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import pickle

class GoogleDriveManager:
    def __init__(self):
        # Portée des autorisations (lecture et écriture)
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Authentification avec Google Drive API"""
        creds = None
        
        # Le fichier token.pickle stocke les tokens d'accès et de rafraîchissement
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # Si il n'y a pas de credentials valides, demander à l'utilisateur de se connecter
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Sauvegarder les credentials pour la prochaine exécution
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('drive', 'v3', credentials=creds)
        print("✅ Authentification réussie avec Google Drive")
    
    def lister_fichiers(self, dossier_id=None, nom_dossier=None):
        """
        Lister tous les fichiers dans un répertoire
        
        Args:
            dossier_id (str): ID du dossier (optionnel)
            nom_dossier (str): Nom du dossier à rechercher (optionnel)
        
        Returns:
            list: Liste des fichiers avec leurs informations
        """
        try:
            # Si un nom de dossier est fourni, trouver son ID
            if nom_dossier and not dossier_id:
                dossier_id = self.trouver_dossier_par_nom(nom_dossier)
                if not dossier_id:
                    print(f"❌ Dossier '{nom_dossier}' non trouvé")
                    return []
            
            # Construire la requête
            if dossier_id:
                query = f"'{dossier_id}' in parents and trashed=false"
            else:
                query = "trashed=false"
            
            # Exécuter la requête
            results = self.service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, size, createdTime)"
            ).execute()
            
            items = results.get('files', [])
            
            if not items:
                print('📁 Aucun fichier trouvé.')
                return []
            
            print(f'📋 {len(items)} fichiers trouvés:')
            print('-' * 80)
            
            for item in items:
                taille = item.get('size', 'N/A')
                if taille != 'N/A':
                    taille = f"{int(taille):,} octets"
                
                print(f"📄 {item['name']}")
                print(f"   ID: {item['id']}")
                print(f"   Type: {item['mimeType']}")
                print(f"   Taille: {taille}")
                print(f"   Créé: {item.get('createdTime', 'N/A')}")
                print('-' * 80)
            
            return items
            
        except Exception as e:
            print(f"❌ Erreur lors de la liste des fichiers: {str(e)}")
            return []
    
    def trouver_dossier_par_nom(self, nom_dossier):
        """Trouver l'ID d'un dossier par son nom"""
        try:
            results = self.service.files().list(
                q=f"name='{nom_dossier}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            items = results.get('files', [])
            if items:
                return items[0]['id']
            return None
            
        except Exception as e:
            print(f"❌ Erreur lors de la recherche du dossier: {str(e)}")
            return None
    
    def telecharger_fichier(self, fichier_id, nom_fichier_local=None, format_export=None):
        """
        Télécharger un fichier depuis Google Drive
        
        Args:
            fichier_id (str): ID du fichier à télécharger
            nom_fichier_local (str): Nom du fichier local (optionnel)
            format_export (str): Format d'export pour les fichiers Google Docs (optionnel)
        
        Returns:
            bool: True si succès, False sinon
        """
        try:
            # Obtenir les métadonnées du fichier
            file_metadata = self.service.files().get(fileId=fichier_id).execute()
            mime_type = file_metadata['mimeType']
            
            if not nom_fichier_local:
                nom_fichier_local = file_metadata['name']
            
            print(f"📥 Téléchargement de '{file_metadata['name']}'...")
            print(f"🔍 Type MIME: {mime_type}")
            
            # Vérifier si c'est un fichier Google Docs/Sheets/Slides
            google_docs_types = {
                'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
                'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
                'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # .pptx
                'application/vnd.google-apps.drawing': 'image/png',  # .png
            }
            
            # Extensions correspondantes
            extensions = {
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
                'image/png': '.png',
                'application/pdf': '.pdf',
                'text/plain': '.txt',
                'text/csv': '.csv'
            }
            
            if mime_type in google_docs_types:
                # C'est un fichier Google Docs - utiliser l'export
                export_mime_type = format_export or google_docs_types[mime_type]
                
                print(f"📄 Fichier Google Docs détecté - Export en format: {export_mime_type}")
                
                # Ajouter l'extension appropriée si elle n'est pas présente
                if export_mime_type in extensions:
                    ext = extensions[export_mime_type]
                    if not nom_fichier_local.lower().endswith(ext.lower()):
                        nom_fichier_local += ext
                
                # Exporter le fichier
                request = self.service.files().export_media(fileId=fichier_id, mimeType=export_mime_type)
                
                # Télécharger directement sans MediaIoBaseDownload pour l'export
                content = request.execute()
                
                with open(nom_fichier_local, 'wb') as f:
                    f.write(content)
                
                print(f"✅ Fichier Google Docs exporté avec succès: {nom_fichier_local}")
                return True
                
            else:
                # Fichier binaire normal - utiliser get_media
                print(f"📁 Fichier binaire détecté - Téléchargement direct")
                
                request = self.service.files().get_media(fileId=fichier_id)
                
                # Créer un buffer pour recevoir les données
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    if status:
                        print(f"⏳ Téléchargement: {int(status.progress() * 100)}%")
                
                # Écrire le fichier sur le disque
                with open(nom_fichier_local, 'wb') as f:
                    fh.seek(0)
                    f.write(fh.read())
                
                print(f"✅ Fichier téléchargé avec succès: {nom_fichier_local}")
                return True
            
        except Exception as e:
            print(f"❌ Erreur lors du téléchargement: {str(e)}")
            return False
    
    def uploader_fichier(self, chemin_fichier_local, dossier_id=None, nom_dossier=None):
        """
        Uploader un fichier vers Google Drive
        
        Args:
            chemin_fichier_local (str): Chemin du fichier local
            dossier_id (str): ID du dossier de destination (optionnel)
            nom_dossier (str): Nom du dossier de destination (optionnel)
        
        Returns:
            str: ID du fichier uploadé si succès, None sinon
        """
        try:
            if not os.path.exists(chemin_fichier_local):
                print(f"❌ Fichier local non trouvé: {chemin_fichier_local}")
                return None
            
            # Si un nom de dossier est fourni, trouver son ID
            if nom_dossier and not dossier_id:
                dossier_id = self.trouver_dossier_par_nom(nom_dossier)
                if not dossier_id:
                    print(f"❌ Dossier '{nom_dossier}' non trouvé")
                    return None
            
            # Préparer les métadonnées du fichier
            nom_fichier = os.path.basename(chemin_fichier_local)
            file_metadata = {'name': nom_fichier}
            
            # Spécifier le dossier parent si fourni
            if dossier_id:
                file_metadata['parents'] = [dossier_id]
            
            # Créer l'objet média pour l'upload
            media = MediaFileUpload(chemin_fichier_local, resumable=True)
            
            print(f"📤 Upload de '{nom_fichier}' en cours...")
            
            # Exécuter l'upload
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            print(f"✅ Fichier uploadé avec succès. ID: {file.get('id')}")
            return file.get('id')
            
        except Exception as e:
            print(f"❌ Erreur lors de l'upload: {str(e)}")
            return None
    
    def obtenir_formats_export(self, fichier_id):
        """
        Obtenir les formats d'export disponibles pour un fichier Google Docs
        
        Args:
            fichier_id (str): ID du fichier
        
        Returns:
            dict: Formats d'export disponibles
        """
        try:
            file_metadata = self.service.files().get(fileId=fichier_id).execute()
            mime_type = file_metadata['mimeType']
            
            # Formats d'export courants pour chaque type de fichier Google
            formats_disponibles = {
                'application/vnd.google-apps.document': {
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx (Word)',
                    'application/pdf': '.pdf',
                    'text/plain': '.txt',
                    'application/rtf': '.rtf',
                    'application/vnd.oasis.opendocument.text': '.odt'
                },
                'application/vnd.google-apps.spreadsheet': {
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx (Excel)',
                    'application/pdf': '.pdf',
                    'text/csv': '.csv',
                    'application/vnd.oasis.opendocument.spreadsheet': '.ods'
                },
                'application/vnd.google-apps.presentation': {
                    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx (PowerPoint)',
                    'application/pdf': '.pdf',
                    'image/jpeg': '.jpg',
                    'image/png': '.png',
                    'application/vnd.oasis.opendocument.presentation': '.odp'
                },
                'application/vnd.google-apps.drawing': {
                    'image/png': '.png',
                    'image/jpeg': '.jpg',
                    'image/svg+xml': '.svg',
                    'application/pdf': '.pdf'
                }
            }
            
            if mime_type in formats_disponibles:
                print(f"📋 Formats d'export disponibles pour '{file_metadata['name']}':")
                for format_mime, description in formats_disponibles[mime_type].items():
                    print(f"   • {format_mime} → {description}")
                return formats_disponibles[mime_type]
            else:
                print(f"📁 Fichier binaire - pas besoin d'export: {mime_type}")
                return {}
                
        except Exception as e:
            print(f"❌ Erreur lors de l'obtention des formats: {str(e)}")
            return {}

    def creer_dossier(self, nom_dossier, dossier_parent_id=None):
        """
        Créer un nouveau dossier dans Google Drive
        
        Args:
            nom_dossier (str): Nom du dossier à créer
            dossier_parent_id (str): ID du dossier parent (optionnel)
        
        Returns:
            str: ID du dossier créé si succès, None sinon
        """
        try:
            file_metadata = {
                'name': nom_dossier,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if dossier_parent_id:
                file_metadata['parents'] = [dossier_parent_id]
            
            file = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            print(f"✅ Dossier '{nom_dossier}' créé avec succès. ID: {file.get('id')}")
            return file.get('id')
            
        except Exception as e:
            print(f"❌ Erreur lors de la création du dossier: {str(e)}")
            return None


def main():
    """Fonction principale avec exemples d'utilisation"""
    
    # Créer une instance du gestionnaire Google Drive
    drive_manager = GoogleDriveManager()
    
    print("\n" + "="*50)
    print("🚀 GESTIONNAIRE GOOGLE DRIVE")
    print("="*50)
    
    # Exemple 1: Lister tous les fichiers dans le drive
    print("\n1️⃣ Liste de tous les fichiers:")
    fichiers = drive_manager.lister_fichiers()
    
    # Exemple 2: Lister les fichiers dans un dossier spécifique
    print("\n2️⃣ Liste des fichiers dans un dossier (exemple: 'Mon Dossier'):")
    # drive_manager.lister_fichiers(nom_dossier="Mon Dossier")
    
    # Exemple 3: Télécharger un fichier (décommentez et remplacez l'ID)
    print("\n3️⃣ Téléchargement d'un fichier:")
    # Pour un fichier normal (PDF, image, etc.)
    # drive_manager.telecharger_fichier("REMPLACER_PAR_ID_FICHIER", "fichier_telecharge.pdf")
    
    # Pour un fichier Google Docs (avec format par défaut)
    # drive_manager.telecharger_fichier("REMPLACER_PAR_ID_GOOGLE_DOCS")
    
    # Pour un fichier Google Docs avec format spécifique
    # drive_manager.telecharger_fichier("REMPLACER_PAR_ID_GOOGLE_DOCS", "mon_document.pdf", "application/pdf")
    
    # Voir les formats disponibles pour un fichier Google Docs
    # drive_manager.obtenir_formats_export("REMPLACER_PAR_ID_GOOGLE_DOCS")
    
    # Exemple 4: Uploader un fichier
    print("\n4️⃣ Upload d'un fichier:")
    # drive_manager.uploader_fichier("chemin/vers/votre/fichier.txt")
    
    # Exemple 5: Uploader un fichier dans un dossier spécifique
    print("\n5️⃣ Upload dans un dossier spécifique:")
    # drive_manager.uploader_fichier("chemin/vers/votre/fichier.txt", nom_dossier="Mon Dossier")
    
    print("\n✨ Terminé!")


if __name__ == "__main__":
    main()