FROM astrocrpublic.azurecr.io/runtime:3.3-4

RUN python -m venv dbt_venv && \
    ./dbt_venv/bin/pip install --no-cache-dir dbt-core dbt-clickhouse && \
    ./dbt_venv/bin/pip freeze | grep -E "^dbt"

# Creo un venv per installare le dipendenze di dbt in modo da non dovermi preoccupare dell'incompatibilità tra le versioni di dbt e astro
# *1 && Fa in modo che o funziona tutto oppure non funziona nulla
# *2 ./dbt_venv/bin/pip install --no-cache-dir dbt-core dbt-clickhouse installa dbt-core e dbt-clickhouse nel venv creato
# *3 Teoricamente dbt-clickhouse dovrebbe installare anche dbt-core, ma per sicurezza lo installo anche esplicitamente perchè voglio pinnarlo.
# *4 ./dbt_venv/bin/pip freeze | grep -E "^dbt" mi fa vedere le versioni installate in modo da pinnarle esplicitamente.