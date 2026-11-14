NEURAPOLIS - CIVIL PROTECTION AGENT
==================================

CONTENUTO
---------
agents/civil_protection/
  __init__.py
  civil_protection_agent.py
  specialists/
    __init__.py
    official_alert_agent.py
    risk_analysis_agent.py
    territorial_impact_agent.py
    safety_assessment_agent.py
  tests/
    __init__.py
    test_civil_protection_agent.py
    test_official_alert_agent.py
    test_risk_analysis_agent.py
    test_territorial_impact_agent.py
    test_safety_assessment_agent.py

INSTALLAZIONE
-------------
1. Estrai lo ZIP.
2. Copia la cartella "civil_protection" dentro:
   backend/agents/

3. Verifica che esista:
   backend/agents/civil_protection/civil_protection_agent.py

4. Non sostituire:
   - services/database.py
   - services/pdf_alert_parser.py
   - services/official_alert_storage.py
   - agents/verification_agent.py
   - agents/social_intelligence_agent.py
   - agents/mobility/

ESECUZIONE TEST
---------------
Apri PowerShell nella cartella backend, attiva il virtualenv già usato
dal progetto e lancia:

python -m agents.civil_protection.tests.test_official_alert_agent
python -m agents.civil_protection.tests.test_risk_analysis_agent
python -m agents.civil_protection.tests.test_territorial_impact_agent
python -m agents.civil_protection.tests.test_safety_assessment_agent
python -m agents.civil_protection.tests.test_civil_protection_agent

ESECUZIONE CON DATABASE
-----------------------
Dalla cartella backend:

python -m agents.civil_protection.civil_protection_agent

Il comando legge le allerte dalle tabelle già esistenti:
- official_alerts
- official_alert_zones

ATTENZIONE
----------
I test usano dati sintetici per controllare il comportamento del codice.
Il test di integrazione non scarica bollettini e non prova l'acquisizione
live di fonti esterne.

Le date senza fuso orario sono interpretate come orari locali italiani.
Le aree sono mantenute come testo ufficiale: non vengono create coordinate
o confini geografici che non siano presenti nei dati.

Il Civil Protection Agent fornisce supporto informativo. Non invia soccorsi,
non dispone evacuazioni e non sostituisce le autorità competenti.
