import pandas as pd

# --- Charger le CSV source ---
df = pd.read_csv("database.csv")  # Remplace par ton fichier

# --- Filtrer uniquement les textes humains ---
df_humans = df[df["generated"] == 0]

# --- Créer le nouveau DataFrame pour le format voulu ---
output = pd.DataFrame({
    "v1": "neutral",           # label pour humain
    "v2": df_humans["text"],   # texte original
    "v3": "",                  # colonnes v3 à v5 vides
    "v4": "",
    "v5": ""
})

# --- Sauvegarder dans un CSV ---
output.to_csv("data.csv", index=False, quoting=1)  # quoting=1 pour mettre les guillemets autour des textes

print("Fichier CSV 'neutral_output.csv' généré avec succès !")
