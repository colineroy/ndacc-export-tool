STRINGS = {
    "en": {
        "app_title":             "raw_to_woudc - WOUDC Export Tool",
        "tab_export":            "WOUDC Export",
        "tab_nasaaims":          "NASA AIMS",
        "tab_metadata":          "Metadata Tables",
        "tab_about":             "About",
        "lang_en":               "English",
        "lang_fi":               "Suomi",
        "lang_fr":               "Français",
        "input_dir":             "Input directory",
        "output_dir":            "Output directory",
        "station":               "Station",
        "station_sdk":           "Sodankylä",
        "station_mr":            "Marambio",
        "options":               "Options",
        "version":               "WOUDC version",
        "advanced":              "Advanced\u2026",
        "apply_dqa":             "Apply DQA corrections",
        "manual_params":         "Edit manual parameters…",
        "run":                   "Run",
        "run_aims":              "Export NASA AIMS",
        "generate":              "Generate",
        "writing_aims":          "Writing NASA AIMS files",
        "aims_written":          "NASA AIMS file(s) generated",
        "browse":                "Browse…",
        "output_prefix":         "Output prefix",
        "summary_ok":            "OK",
        "summary_err":           "errors",
        "summary_nobrewer":      "flights without Brewer normalization",
        "total":                 "Total profiles processed",
        "woudc_written":         "WOUDC file(s) generated",
        "tables_written":        "Table(s) written",
        "elapsed":               "Elapsed",
        "no_files":              "No matching files found in input directory.",
        "not_found":             "does not exist",
        "choose_input":          "Select input directory",
        "choose_output":         "Select output directory",
        "choose_output_file":    "Select output file",
        "cancel":                "Cancel",
        "save":                  "Save",
        "close":                 "Close",
        "csv_filter":            "CSV files (*.csv)",
        "xlsx_filter":           "Excel files (*.xlsx)",
        "all_filter":            "All files (*.*)",
        "select_all":            "Select All",
        "deselect_all":          "Deselect All",
        "filename":              "Filename",
        "processing":            "Processing",
        "writing":               "Writing WOUDC files",
        "done":                  "Done",
        "about_title":           "About raw_to_woudc",
        "about_intro":           (
            "raw_to_woudc converts raw ozonesonde files from Sodankylä"
            " (SHARP and NOG-DB formats) and Marambio (MR format) into"
            " WOUDC extCSV format with DQA homogenization.\n\n"
        ),
        "about_sources":         "Data sources",
        "about_sources_text":    (
            "• SHARP (*.q*): Vaisala SHARP text files from the FMI Sodankylä"
            " station (2024–present).\n"
            "• NOG-DB (*.F*, *.j*, *.K*, …): Legacy NOG-DB format files from"
            " the FMI Sodankylä station (1988–1994).\n"
            "• MR (*.txt): NOG-DB variant files from the Marambio station"
            " (2019–2022).\n"
        ),
        "about_dqa":             "DQA corrections",
        "about_dqa_text":        (
            "1. Background current subtraction (bg_post_ua).\n"
            "2. Pump efficiency correction using the STOIC 1989 table"
            " (Komhyr et al., 1995).\n"
            "3. Transfer function correction (Deshler et al., 2017"
            " - DMT-Z / SST 0.5%%).\n"
            "4. Brewer total column normalization"
            " (CorrectionCode=8 with Brewer, 6 without).\n"
        ),
        "about_woudc":           "WOUDC extCSV format",
        "about_woudc_text":      (
            "The output follows the WOUDC OzoneSonde extCSV specification:"
            " blocks for content header, platform, instrument, location,"
            " timestamp, flight summary, auxiliary data, ozone reference"
            " (Brewer), pump correction table, and the 11-column profile.\n"
        ),
        "about_refs":            "References",
        "about_refs_text":       (
            "• Komhyr, W. D. (1969). Electrochemical concentration cells"
            " for gas analysis. Ann. Geophys., 25, 203–210.\n"
            "• Komhyr, W. D. et al. (1995). Electrochemical concentration"
            " cell ozonesonde performance. JGR, 100(D5), 9231–9244.\n"
            "• Deshler, T. et al. (2017). Atmospheric comparison of"
            " electrochemical cell ozonesondes. AMT, 10, 3955–3978.\n"
            "• WOUDC Data Format: https://woudc.org/\n"
        ),
    },

    "fi": {
        "app_title":             "raw_to_woudc - WOUDC-työkalu",
        "tab_export":            "WOUDC-vienti",
        "tab_nasaaims":          "NASA AIMS",
        "tab_metadata":          "Metatietotaulukot",
        "tab_about":             "Tietoja",
        "lang_en":               "English",
        "lang_fi":               "Suomi",
        "lang_fr":               "Français",
        "input_dir":             "Syöttökansio",
        "output_dir":            "Tuloskansio",
        "station":               "Asema",
        "station_sdk":           "Sodankylä",
        "station_mr":            "Marambio",
        "options":               "Asetukset",
        "version":               "WOUDC-versio",
        "advanced":              "Lisäasetukset\u2026",
        "apply_dqa":             "Käytä DQA-korjauksia",
        "manual_params":         "Muokkaa manuaalisia parametreja…",
        "run":                   "Suorita",
        "run_aims":              "Vie NASA AIMS",
        "generate":              "Luo",
        "writing_aims":          "Kirjoitetaan NASA AIMS -tiedostoja",
        "aims_written":          "NASA AIMS -tiedosto(a) luotu",
        "browse":                "Selaa…",
        "output_prefix":         "Tulostiedoston etuliite",
        "summary_ok":            "OK",
        "summary_err":           "virhettä",
        "summary_nobrewer":      "lentoa ilman Brewer-normalisointia",
        "total":                 "Profilleja yhteensä",
        "woudc_written":         "WOUDC-tiedosto(a) luotu",
        "tables_written":        "Taulukko(a) kirjoitettu",
        "elapsed":               "Kului",
        "no_files":              "Ei sopivia tiedostoja syöttökansiossa.",
        "not_found":             "ei ole olemassa",
        "choose_input":          "Valitse syöttökansio",
        "choose_output":         "Valitse tuloskansio",
        "choose_output_file":    "Valitse tulostiedosto",
        "cancel":                "Peruuta",
        "save":                  "Tallenna",
        "close":                 "Sulje",
        "csv_filter":            "CSV-tiedostot (*.csv)",
        "xlsx_filter":           "Excel-tiedostot (*.xlsx)",
        "all_filter":            "Kaikki tiedostot (*.*)",
        "select_all":            "Valitse kaikki",
        "deselect_all":          "Poista valinnat",
        "filename":              "Tiedostonimi",
        "processing":            "Käsitellään",
        "writing":               "Kirjoitetaan WOUDC-tiedostoja",
        "done":                  "Valmis",
        "about_title":           "Tietoja raw_to_woudc:stä",
        "about_intro":           (
            "raw_to_woudc muuntaa Sodankylän (SHARP- ja NOG-DB-muodot)"
            " ja Marambion (MR-muoto) raakaotosonditiedostot"
            " WOUDC extCSV -muotoon DQA-homogenisoinnilla.\n\n"
        ),
        "about_sources":         "Tietolähteet",
        "about_sources_text":    (
            "• SHARP (*.q*): Vaisala SHARP -tekstitiedostot Sodankylän"
            " FMI-asemalta (2024–).\n"
            "• NOG-DB (*.F*, *.j*, *.K*, …): Vanhat NOG-DB-muotoiset"
            " tiedostot Sodankylän FMI-asemalta (1988–1994).\n"
            "• MR (*.txt): NOG-DB-muunnelmatiedostot Marambio-asemalta"
            " (2019–2022).\n"
        ),
        "about_dqa":             "DQA-korjaukset",
        "about_dqa_text":        (
            "1. Taustavirran vähennys (bg_post_ua).\n"
            "2. Pumpputehokkuuden korjaus STOIC 1989 -taulukolla"
            " (Komhyr et al., 1995).\n"
            "3. Siirtofunktiokorjaus (Deshler et al., 2017"
            " - DMT-Z / SST 0.5%%).\n"
            "4. Brewer-kokonaispatsasnormalisointi"
            " (CorrectionCode=8 Brewerillä, 6 ilman).\n"
        ),
        "about_woudc":           "WOUDC extCSV -muoto",
        "about_woudc_text":      (
            "Tulos noudattaa WOUDC OzoneSonde extCSV -määrittelyä:"
            " lohkot otsikolle, alustalle, instrumentille, sijainnille,"
            " aikaleimalle, lentoyhteenvedolle, apudatalle,"
            " otsoniviitteelle (Brewer), pumppukorjaustaulukolle"
            " ja 11-sarakkeiselle profiilille.\n"
        ),
        "about_refs":            "Viitteet",
        "about_refs_text":       (
            "• Komhyr, W. D. (1969). Electrochemical concentration cells"
            " for gas analysis. Ann. Geophys., 25, 203–210.\n"
            "• Komhyr, W. D. et al. (1995). Electrochemical concentration"
            " cell ozonesonde performance. JGR, 100(D5), 9231–9244.\n"
            "• Deshler, T. et al. (2017). Atmospheric comparison of"
            " electrochemical cell ozonesondes. AMT, 10, 3955–3978.\n"
            "• WOUDC Data Format: https://woudc.org/\n"
        ),
    },

    "fr": {
        "app_title":             "raw_to_woudc - Outil d'export WOUDC",
        "tab_export":            "Export WOUDC",
        "tab_nasaaims":          "NASA AIMS",
        "tab_metadata":          "Tables de métadonnées",
        "tab_about":             "À propos",
        "lang_en":               "English",
        "lang_fi":               "Suomi",
        "lang_fr":               "Français",
        "input_dir":             "Dossier d'entrée",
        "output_dir":            "Dossier de sortie",
        "station":               "Station",
        "station_sdk":           "Sodankylä",
        "station_mr":            "Marambio",
        "options":               "Options",
        "version":               "Version WOUDC",
        "advanced":              "Avancé\u2026",
        "apply_dqa":             "Appliquer les corrections DQA",
        "manual_params":         "Modifier les paramètres manuels…",
        "run":                   "Exécuter",
        "run_aims":              "Exporter NASA AIMS",
        "generate":              "Générer",
        "writing_aims":          "Écriture des fichiers NASA AIMS",
        "aims_written":          "Fichier(s) NASA AIMS généré(s)",
        "browse":                "Parcourir…",
        "output_prefix":         "Préfixe de sortie",
        "summary_ok":            "OK",
        "summary_err":           "erreurs",
        "summary_nobrewer":      "vols sans normalisation Brewer",
        "total":                 "Profils traités au total",
        "woudc_written":         "Fichier(s) WOUDC généré(s)",
        "tables_written":        "Tableau(x) écrit(s)",
        "elapsed":               "Temps écoulé",
        "no_files":              "Aucun fichier correspondant dans le dossier d'entrée.",
        "not_found":             "n'existe pas",
        "choose_input":          "Choisir le dossier d'entrée",
        "choose_output":         "Choisir le dossier de sortie",
        "choose_output_file":    "Choisir le fichier de sortie",
        "cancel":                "Annuler",
        "save":                  "Enregistrer",
        "close":                 "Fermer",
        "csv_filter":            "Fichiers CSV (*.csv)",
        "xlsx_filter":           "Fichiers Excel (*.xlsx)",
        "all_filter":            "Tous les fichiers (*.*)",
        "select_all":            "Tout sélectionner",
        "deselect_all":          "Tout désélectionner",
        "filename":              "Fichier",
        "processing":            "Traitement",
        "writing":               "Écriture des fichiers WOUDC",
        "done":                  "Terminé",
        "about_title":           "À propos de raw_to_woudc",
        "about_intro":           (
            "raw_to_woudc convertit les fichiers bruts de radiosondes"
            " ozoniques de Sodankylä (formats SHARP et NOG-DB) et"
            " de Marambio (format MR) au format WOUDC extCSV avec"
            " homogénéisation DQA.\n\n"
        ),
        "about_sources":         "Sources de données",
        "about_sources_text":    (
            "• SHARP (*.q*): Fichiers texte Vaisala SHARP de la station"
            " FMI Sodankylä (2024–présent).\n"
            "• NOG-DB (*.F*, *.j*, *.K*, …): Fichiers au format NOG-DB"
            " historique de la station FMI Sodankylä (1988–1994).\n"
            "• MR (*.txt): Variante du format NOG-DB pour la station"
            " Marambio (2019–2022).\n"
        ),
        "about_dqa":             "Corrections DQA",
        "about_dqa_text":        (
            "1. Soustraction du courant de fond (bg_post_ua).\n"
            "2. Correction d'efficacité de pompe avec la table STOIC 1989"
            " (Komhyr et al., 1995).\n"
            "3. Correction de fonction de transfert (Deshler et al., 2017"
            " - DMT-Z / SST 0.5%%).\n"
            "4. Normalisation par la colonne totale Brewer"
            " (CorrectionCode=8 avec Brewer, 6 sans).\n"
        ),
        "about_woudc":           "Format WOUDC extCSV",
        "about_woudc_text":      (
            "La sortie suit la spécification WOUDC OzoneSonde extCSV :"
            " blocs pour l'en-tête, la plateforme, l'instrument,"
            " la localisation, l'horodatage, le résumé de vol,"
            " les données auxiliaires, la référence ozone (Brewer),"
            " la table de correction de pompe et le profil"
            " à 11 colonnes.\n"
        ),
        "about_refs":            "Références",
        "about_refs_text":       (
            "• Komhyr, W. D. (1969). Electrochemical concentration cells"
            " for gas analysis. Ann. Geophys., 25, 203–210.\n"
            "• Komhyr, W. D. et al. (1995). Electrochemical concentration"
            " cell ozonesonde performance. JGR, 100(D5), 9231–9244.\n"
            "• Deshler, T. et al. (2017). Atmospheric comparison of"
            " electrochemical cell ozonesondes. AMT, 10, 3955–3978.\n"
            "• WOUDC Data Format: https://woudc.org/\n"
        ),
    },
}


def _(lang: str, key: str) -> str:
    """Look up a translated string by key."""
    return STRINGS.get(lang, STRINGS["en"]).get(key, f"??{key}??")
