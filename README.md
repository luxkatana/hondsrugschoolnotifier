# Een Hondsrug College Notifier die echt handig is

## Wat doet deze magie??

Deze magie kan de leerling een berichtje sturen voor elke 10 minuten van een les.

## Installatie

Installeer de benodigde modules

```
python -m pip install -r requirements.txt

```


## Configuratie

Momenteel is het alleen mogelijk om de leerling's leerlingnummer en leerling's wachtwoord te zetten. Deze credentials worden gebruikt om de rooster van de leerling te verzamelen via somtoday.

om de leerling's leerlingnummer & wachtwoord te configureren

```
LEERLING_LEERLINGNUMMER=""
LEERLING_WACHTWOORD=""
touch .env
echo "STUDENT_NAME=$LEERLING_LEERLINGNUMMER\nSTUDENT_PASSWORD=$LEERLING_WACHTWOORD\n" >> .env
```

Tot slot gebruikt deze notifier **ntfy** om de bericht te sturen. 
Omdat het **ntfy** gebruikt moet de leerling op zijn apparaat de **ntfy** applicatie hebben.
De leerling moet in de **ntfy** app een **topic** volgen die uniek moet zijn (zodat niemand jouw spamt!)


Om het **topic** vast te stellen configureer je dit in je .env

```
NTFY_TOPIC_NAME="" # 
echo "NTFY_TOPIC_NAME=$NTFY_TOPIC_NAME\n" >> .env
```

En tot slot run je de notifier!
```
python main.py
```


## Extra's

Paar extra features waar ik het meeste tijd heb aan besteed 
<ul> 
<li>Extra activiteiten toevoegen met een custom bericht</li>
</ul>

### Extra informatie (niet echt belangrijk ig)
Ik gebruik meestal <a href='https://www.koyeb.com/'>koyeb</a> om dit te hosten