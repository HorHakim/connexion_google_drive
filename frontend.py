import random
import datetime
import os

from dotenv import load_dotenv
import streamlit as st

from utils_drive import GoogleDriveManager

drive_manager = GoogleDriveManager()
load_dotenv()


st.title("Charger un ancien projet")

dict_file_name_id = drive_manager.gets_files_names_and_ids(dossier_id=os.environ["ID_CTICM_DIRECTORY"])

# liste déroulante contenant la liste des reports sauvegardés
selection = st.selectbox(
    "Choisissez une option :",
    list(dict_file_name_id.keys()),
    index=0  # Index de l'option sélectionnée par défaut (0 = première option)
)


if st.button("Charger le projet", type="primary"):
    with st.spinner("Traitement en cours..."):
        report_object = drive_manager.load_report(fichier_id=dict_file_name_id[selection])
        st.write(f"Vous venez de charger : **{report_object}**")





if st.button("Déposer un objet aléatoire sur le drive", type="primary"):
    with st.spinner("Traitement en cours..."):
        drive_manager.uploader_report(objet_a_pickler=random.randint(0, 2000),\
                                       nom_fichier="sauvegarde",\
                                       dossier_id=id_cticm_repository)

        st.write(f"Vous venez de déposer un objet aléatoire sur le drive")

