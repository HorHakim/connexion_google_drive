import os
import io
import tempfile
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
    
    def gets_files_names_and_ids(self, dossier_id=None, nom_dossier=None, verbose=False):
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
            if verbose:
                print(f'📋 {len(items)} fichiers trouvés:')
                print('-' * 80)
            
            dict_file_name_id = {}
            for item in items:
                dict_file_name_id[f"{item['name'][:-4]}_{item['createdTime'][:-6]}"] = item['id']
                
                taille = item.get('size', 'N/A')
                if taille != 'N/A':
                    taille = f"{int(taille):,} octets"
                if verbose:
                    print(f"📄 {item['name']}")
                    print(f"   ID: {item['id']}")
                    print(f"   Type: {item['mimeType']}")
                    print(f"   Taille: {taille}")
                    print(f"   Créé: {item.get('createdTime', 'N/A')}")
                    print('-' * 80)
                
            return dict_file_name_id
            
        except Exception as e:
            print(f"❌ Erreur lors de la liste des fichiers: {str(e)}")
            return []
    
    def get_directory_id_by_name(self, nom_dossier):
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
    
    def load_report(self, fichier_id, nom_fichier_local=None, format_export=None):
        """
        Charge un objet pkl depuis le drive
        
        Args:
            fichier_id (str): ID du fichier à télécharger
            nom_fichier_local (str): Nom du fichier local (optionnel)
            format_export (str): Format d'export pour les fichiers Google Docs (optionnel)
        
        Returns:
            L'objet chargé depuis de le drive dans notre cas, il s'agit d'un objet de la classe Report
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
            

            # Fichier binaire normal - utiliser get_media
            print(f"📁 Fichier binaire détecté - Téléchargement direct")
            
            request = self.service.files().get_media(fileId=fichier_id)
            
            # Créer un buffer pour recevoir les données
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()

             # IMPORTANT: Reset the buffer position to the beginning
            fh.seek(0)

            report_object = pickle.loads(fh.read())
            print(f"✅ Report chargé avec succès")
            return report_object

            
        except Exception as e:
            print(f"❌ Erreur lors du téléchargement: {str(e)}")
            return False
    
    def uploader_report(self, chemin_fichier_local=None, report_object=None, nom_fichier=None, dossier_id=None, nom_dossier=None):
        """
        Uploader un fichier vers Google Drive (fichier existant ou objet à pickler)
        
        Args:
            chemin_fichier_local (str): Chemin du fichier local (optionnel)
            report_object (any): Objet Python à pickler et uploader (optionnel)
            nom_fichier (str): Nom du fichier de destination (requis si report_object)
            dossier_id (str): ID du dossier de destination (optionnel)
            nom_dossier (str): Nom du dossier de destination (optionnel)
        
        Returns:
            str: ID du fichier uploadé si succès, None sinon
        """
        try:
            # Vérifier qu'un seul mode est utilisé
            if chemin_fichier_local and report_object is not None:
                print("❌ Vous devez spécifier soit 'chemin_fichier_local' soit 'report_object', pas les deux")
                return None
            
            if not chemin_fichier_local and report_object is None:
                print("❌ Vous devez spécifier soit 'chemin_fichier_local' soit 'report_object'")
                return None
            
            # Si un nom de dossier est fourni, trouver son ID
            if nom_dossier and not dossier_id:
                dossier_id = self.trouver_dossier_par_nom(nom_dossier)
                if not dossier_id:
                    print(f"❌ Dossier '{nom_dossier}' non trouvé")
                    return None
            
            temp_file_path = None  # Pour le nettoyage
            
            # Mode 1: Upload d'un fichier existant
            if chemin_fichier_local:
                if not os.path.exists(chemin_fichier_local):
                    print(f"❌ Fichier local non trouvé: {chemin_fichier_local}")
                    return None
                
                # Préparer les métadonnées du fichier
                nom_final = nom_fichier or os.path.basename(chemin_fichier_local)
                file_metadata = {'name': nom_final}
                
                # Spécifier le dossier parent si fourni
                if dossier_id:
                    file_metadata['parents'] = [dossier_id]
                
                # Créer l'objet média pour l'upload
                media = MediaFileUpload(chemin_fichier_local, resumable=True)
                
                print(f"📤 Upload du fichier '{nom_final}' en cours...")
                
            # Mode 2: Pickle d'un objet et upload
            else:
                if not nom_fichier:
                    print("❌ Le paramètre 'nom_fichier' est requis lors de l'upload d'un objet pickle")
                    return None
                
                # Ajouter l'extension .pkl si elle n'est pas présente
                if not nom_fichier.lower().endswith('.pkl'):
                    nom_final = f"{nom_fichier}.pkl"
                else:
                    nom_final = nom_fichier
                
                print(f"🥒 Pickl-ification de l'objet en cours...")
                
                # Créer un fichier temporaire pour le pickle
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as temp_file:
                    pickle.dump(report_object, temp_file)
                    temp_file_path = temp_file.name
                
                # Préparer les métadonnées du fichier
                file_metadata = {'name': nom_final}
                
                # Spécifier le dossier parent si fourni
                if dossier_id:
                    file_metadata['parents'] = [dossier_id]
                
                # Créer l'objet média pour l'upload depuis le fichier temporaire
                media = MediaFileUpload(temp_file_path, resumable=True)
                
                print(f"📤 Upload de l'objet pickl-é '{nom_final}' en cours...")
            
            # Exécuter l'upload (commun aux deux modes)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            # Nettoyer le fichier temporaire si c'était un pickle
            if temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            
            print(f"✅ Fichier uploadé avec succès. ID: {file.get('id')}")
            return file.get('id')
            
        except Exception as e:
            # Nettoyer le fichier temporaire en cas d'erreur
            if 'temp_file_path' in locals() and temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            print(f"❌ Erreur lors de l'upload: {str(e)}")
            return None
