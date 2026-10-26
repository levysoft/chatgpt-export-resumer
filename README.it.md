# ChatGPT Export Resumer

[English](README.md) | [Italiano](README.it.md)

**Riprende i download interrotti degli export di ChatGPT e recupera gli archivi ZIP che sembrano corrotti.**

ChatGPT Export Resumer è uno strumento Python da riga di comando che utilizza una richiesta autenticata copiata da Chrome, riduce i cookie non necessari e scarica lo ZIP tramite `curl`. Se l'esportazione è incompleta, prova a riprendere il trasferimento e verifica l'integrità dell'archivio prima di estrarlo. **Non richiede pacchetti Python esterni.**

Sviluppato da **Antonio Troise (Levysoft)**. Una volta preparato `chrome-curl.txt` con gli strumenti per sviluppatori di Chrome, puoi eseguire:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract
```

## Perché esiste questo strumento

A volte il download dell'esportazione dei dati di ChatGPT si completa solo parzialmente.

Il file può sembrare uno ZIP:

```bash
file chatgpt-export.zip
```

Esempio:

```text
chatgpt-export.zip: Zip archive data, at least v2.0 to extract, compression method=deflate
```

Ma il controllo con `unzip` fallisce:

```bash
unzip -t chatgpt-export.zip
```

Esempio:

```text
End-of-central-directory signature not found.
Either this file is not a zipfile, or it constitutes one disk of a multi-part archive.
```

In genere significa che l'inizio dello ZIP è presente, ma manca la parte finale del file.

Negli archivi ZIP, la directory centrale (*central directory*) si trova alla fine del file. Se il download viene troncato, il file può comunque iniziare come un vero ZIP, ma strumenti come `unzip` non riescono ad aprirlo perché manca l'indice finale.

Questo script automatizza la procedura di recupero:

1. Legge un comando **Copy as cURL** copiato da Chrome.
2. Estrae l'URL dell'export di ChatGPT.
3. Estrae i cookie dalla richiesta del browser.
4. Elimina i cookie non necessari, come `conv_key_*`.
5. Scarica l'archivio ZIP usando `curl`.
6. Verifica l'archivio con `unzip -t`.
7. Cerca le firme finali dello ZIP:
   - EOCD normale;
   - EOCD ZIP64;
   - ZIP64 locator.
8. Se il file è incompleto, riprende il download con `curl -C -`.
9. Genera un report tecnico con i dati sensibili oscurati.
10. Facoltativamente, estrae lo ZIP e apre `chat.html`.

## Funzionalità

- **Download autenticato**: legge URL e cookie dell'export di ChatGPT dalla richiesta **Copy as cURL** di Chrome.
- **Pulizia dei cookie**: rimuove quelli superflui, come `conv_key_*`, e conserva quelli generalmente utili per la richiesta.
- **Ripresa automatica**: continua i download incompleti con `curl -C -`, senza ricominciare da zero se il server supporta le richieste per intervalli di byte.
- **Verifica ZIP**: controlla l'archivio con `unzip` (oppure con `zipfile` di Python) e cerca le firme EOCD/ZIP64.
- **Output configurabile**: modalità dettagliata o silenziosa, controllo dell'avanzamento, report diagnostici, estrazione facoltativa e apertura di `chat.html` su macOS.
- **Pulizia dei file temporanei**: l'opzione `--cleanup` elimina file temporanei e diagnostici anche senza avviare un download.

Lo strumento non aggira l'autenticazione di ChatGPT. Occorrono un link di esportazione valido e una richiesta autenticata del browser; il recupero dipende inoltre dal supporto del server per la ripresa dei download.

## Informazioni ufficiali

OpenAI invia le esportazioni dei dati di ChatGPT tramite email. Il link per il download scade dopo 24 ore e il file scaricato dovrebbe essere un archivio ZIP contenente la cronologia delle chat e altri dati dell'account.

Riferimento: [Guida OpenAI per esportare i dati di ChatGPT](https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data).

OpenAI avverte inoltre che i file diagnostici, come i file HAR, possono contenere informazioni personali o sensibili. Lo stesso principio vale per i comandi **Copy as cURL** copiati da Chrome, perché possono includere cookie, URL temporanei firmati e token di sessione.

Riferimento: [Guida OpenAI per contattare il supporto](https://help.openai.com/en/articles/6614161-how-can-i-contact-support).

## Requisiti

- macOS, Linux o un altro ambiente Unix-like
- Python 3.9 o successivo
- `curl`
- `unzip`

Non sono richiesti pacchetti Python esterni.

Su macOS, `python3` è spesso già disponibile se sono installati Xcode o gli Xcode Command Line Tools. La versione può variare, quindi verifica con:

```bash
python3 --version
```

Se necessario, puoi installare una versione più recente di Python tramite Homebrew:

```bash
brew install python
```

## Perché la compatibilità con Python 3.9?

La prima versione dello script utilizzava annotazioni di tipo (*type hints*) come:

```python
Path | None
```

Questa sintassi è supportata a partire da Python 3.10. Con Python 3.9 può generare:

```text
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

Per facilitare l'esecuzione anche sulle configurazioni macOS meno recenti, lo script è stato scritto per funzionare con Python 3.9 e include:

```python
from __future__ import annotations
```

Inoltre, non richiede dipendenze di terze parti.

## Installazione

Clona la repository:

```bash
git clone https://github.com/levysoft/chatgpt-export-resumer.git
cd chatgpt-export-resumer
```

Rendi eseguibile lo script:

```bash
chmod +x chatgpt_export_resumer.py
```

## Come ottenere `chrome-curl.txt`

1. Richiedi l'esportazione dei dati di ChatGPT.
2. Apri in Chrome l'email con il link per scaricare l'export.
3. Apri gli strumenti per sviluppatori di Chrome (*DevTools*):

```text
Cmd + Option + I
```

4. Vai alla scheda **Rete** (*Network*).
5. Attiva **Conserva log** (*Preserve log*).
6. Apri il link per il download dell'export.
7. Individua la richiesta verso un indirizzo simile a:

```text
/backend-api/estuary/content?id=...
```

8. Fai clic con il tasto destro sulla richiesta.
9. Seleziona:

```text
Copy > Copy as cURL
```

10. Salva il comando copiato in un file:

```bash
vi chrome-curl.txt
```

Premi `i` per entrare in modalità inserimento, incolla il comando, poi premi `Esc` e digita `:wq` per salvare e uscire.

**Importante:** non pubblicare `chrome-curl.txt`. Può contenere cookie e token di sessione.

## Utilizzo di base

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract
```

Il comando:

- legge l'URL e i cookie da `chrome-curl.txt`;
- riduce i cookie presenti nell'header della richiesta;
- scarica lo ZIP;
- verifica l'integrità dell'archivio;
- riprende il download, se necessario;
- genera `report-export-chatgpt.txt`;
- estrae l'archivio nella cartella `chatgpt-export-estratto/`.

## Utilizzo consigliato su macOS

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --open-html --quiet --cleanup
```

In aggiunta, questo comando:

- apre `chat.html` dopo l'estrazione;
- elimina i file temporanei e diagnostici;
- conserva `chatgpt-export.zip` e `chatgpt-export-estratto/`.

## Modalità di output

Per impostazione predefinita, lo script mostra informazioni dettagliate durante l'esecuzione.

È utile quando si recuperano esportazioni molto grandi, perché consente di seguire l'avanzamento. Nella modalità standard vengono mostrati:

- la barra di avanzamento di `curl`;
- l'output del controllo `unzip -t`;
- l'output dell'estrazione con messaggi come `inflating: ...`;
- le informazioni diagnostiche su stato HTTP, firme ZIP e dimensione finale.

### Modalità dettagliata (predefinita)

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract
```

Usala quando vuoi vedere tutti i dettagli.

### Modalità silenziosa (`--quiet`)

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --quiet
```

L'opzione `--quiet` nasconde gran parte dell'output più lungo, mostrando soltanto i passaggi principali, gli errori e il riepilogo finale.

Esempio di output:

```text
Download iniziale: HTTP 200, 2.69 GiB
ZIP incompleto: EOCD non trovata
Resume 1/5: HTTP 206, +1.24 GiB
ZIP valido: 3.93 GiB
Export estratto in: chatgpt-export-estratto
Report scritto in: report-export-chatgpt.txt
```

### Modalità senza barra di avanzamento (`--no-progress`)

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --no-progress
```

L'opzione `--no-progress` disattiva soltanto la barra di avanzamento di `curl`, ma mantiene l'output dettagliato relativo alla verifica dello ZIP e all'estrazione.

È utile se il terminale, il file di log o la shell remota non visualizzano correttamente la barra di avanzamento.

## Opzioni

### `curl_file`

Argomento posizionale facoltativo.

Indica il file che contiene il comando **Copy as cURL** copiato da Chrome.

È necessario per le operazioni di download, ripresa, verifica ed estrazione:

```bash
./chatgpt_export_resumer.py chrome-curl.txt
```

**Non è necessario** quando si esegue la sola pulizia in modalità standalone:

```bash
./chatgpt_export_resumer.py --cleanup
```

### `-o`, `--output`

Imposta il nome del file ZIP da creare.

Valore predefinito:

```text
chatgpt-export.zip
```

Esempio:

```bash
./chatgpt_export_resumer.py chrome-curl.txt -o my-export.zip
```

### `--extract`

Estrae l'archivio ZIP dopo che la verifica ne ha confermato la validità.

Esempio:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract
```

Cartella di estrazione predefinita:

```text
chatgpt-export-estratto/
```

### `--extract-dir`

Imposta una cartella di estrazione personalizzata.

Esempio:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --extract-dir export
```

### `--open-html`

Apre `chat.html` dopo l'estrazione.

È particolarmente utile su macOS, dove viene utilizzato il comando `open`.

Esempio:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --open-html
```

### `--http1`

Forza l'utilizzo di HTTP/1.1 da parte di `curl`.

Può essere utile se HTTP/2 presenta comportamenti anomali o si verificano problemi con proxy e connessioni di rete.

Esempio:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --http1
```

### `--force`

Elimina lo ZIP già presente e ricomincia il download da zero.

Senza `--force`, se `chatgpt-export.zip` esiste già, lo script prima ne verifica l'integrità e poi, se necessario, prova a riprendere il download.

Esempio:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --force
```

### `--max-resume`

Imposta il numero massimo di tentativi per riprendere il download.

Valore predefinito:

```text
5
```

Esempio:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --max-resume 10
```

### `--quiet`

Mostra soltanto le informazioni essenziali.

Esempio:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --quiet
```

In modalità silenziosa:

- la barra di avanzamento di `curl` viene nascosta;
- l'output dettagliato di `unzip -t` viene nascosto;
- l'output dell'estrazione viene nascosto;
- il riepilogo finale resta visibile.

### `--no-progress`

Disattiva soltanto la barra di avanzamento di `curl`.

Esempio:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --no-progress
```

A differenza di `--quiet`, continua a mostrare i dettagli della verifica e dell'estrazione dello ZIP.

### `--cleanup`

Elimina i file temporanei e diagnostici, senza modificare lo script, il README, il file ZIP e l'export estratto.

Rimuove:

```text
chrome-curl.txt
cookies-minimi.txt
headers-*.txt
result-*.txt
unzip-extract-result.txt
report-export-chatgpt.txt
.curl-chatgpt-export-*.conf
```

Non rimuove:

```text
chatgpt_export_resumer.py
README.md
README.it.md
chatgpt-export.zip
chatgpt-export-estratto/
```

Al termine della normale procedura di download:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --quiet --cleanup
```

Oppure, per eseguire la sola pulizia dopo un utilizzo precedente:

```bash
./chatgpt_export_resumer.py --cleanup
```

## File generati

### `chatgpt-export.zip`

L'archivio ZIP dell'export scaricato ed eventualmente completato con il resume.

### `chatgpt-export-estratto/`

La cartella in cui viene estratto l'export.

Di solito contiene file come:

```text
chat.html
conversation_asset_file_names.json
conversations-000.json
conversations-001.json
...
library_files.json
message_feedback.json
shared_conversations.json
user.json
user_settings.json
export_manifest.json
```

Le esportazioni più grandi possono suddividere le conversazioni in più file:

```text
conversations-000.json
conversations-001.json
conversations-002.json
...
```

### `report-export-chatgpt.txt`

Un report con i dati sensibili oscurati, contenente:

- dimensione dello ZIP;
- stato delle firme finali dello ZIP;
- header HTTP utili;
- riepilogo dei risultati di `curl`;
- riepilogo dei tentativi di resume;
- riepilogo finale del recupero.

Il report è pensato per poter essere consultato e, dopo averlo verificato, eventualmente condiviso. **Controllalo sempre manualmente prima di pubblicarlo o inviarlo.**

### `cookies-minimi.txt`

File temporaneo sensibile che contiene i cookie ridotti al minimo.

Non pubblicarlo.

Puoi eliminarlo con:

```bash
rm -f cookies-minimi.txt
```

Oppure eseguendo il comando di pulizia standalone:

```bash
./chatgpt_export_resumer.py --cleanup
```

### `headers-*.txt` e `result-*.txt`

File diagnostici.

Nel report generato dallo script i dati vengono oscurati, ma i file originali possono comunque contenere informazioni sensibili, a seconda dell'ambiente.

Verificali prima di condividerli.

## Avvertenze di sicurezza

Il file `chrome-curl.txt` può contenere:

- cookie di sessione;
- URL firmati;
- token temporanei dell'export;
- cookie Cloudflare;
- cookie associati all'account.

**Non devi:**

- includerlo in un commit su GitHub;
- incollarlo su forum pubblici;
- allegarlo alle issue di GitHub;
- condividerlo nelle segnalazioni di bug senza aver rimosso le informazioni sensibili.

Dopo aver completato il recupero, elimina i file sensibili con:

```bash
./chatgpt_export_resumer.py --cleanup
```

Oppure manualmente:

```bash
rm -f chrome-curl.txt cookies-minimi.txt
```

Puoi anche eseguire la pulizia automaticamente alla fine del processo:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --quiet --cleanup
```

Per una maggiore sicurezza, puoi disconnetterti da ChatGPT ed effettuare nuovamente l'accesso.

## `.gitignore` consigliato

```gitignore
chrome-curl.txt
cookies-minimi.txt
headers-*.txt
result-*.txt
unzip-extract-result.txt
report-export-chatgpt.txt
*.zip
chatgpt-export-estratto/
.curl-chatgpt-export-*.conf
```

## Caso reale documentato, modalità `--quiet`

Questo è un log reale, con i dati sensibili oscurati, relativo a un recupero riuscito utilizzando `--quiet`.

Il primo download aveva restituito `HTTP 200` e `application/octet-stream`, ma lo ZIP era incompleto:

```text
ChatGPT Export Resumer
============================================================
URL trovato: https://chatgpt.com/backend-api/estuary/content?[REDACTED_QUERY]
Lunghezza cookie originale: 10043 byte
Lunghezza cookie minima: 7059 byte

Download iniziale...

+ curl https://chatgpt.com/backend-api/estuary/content?[REDACTED_QUERY] [download, config temporaneo, cookie redatti] -o chatgpt-export.zip

HTTP iniziale: 200
Content-Type iniziale: application/octet-stream
Byte scaricati iniziali: 2889875456
Dimensione dopo download iniziale: 2889875456 byte, 2.69 GiB

Verifica ZIP...
ZIP non valido o incompleto secondo unzip.
Firme finali ZIP: EOCD normale=no, EOCD ZIP64=no, ZIP64 locator=no

Tentativo resume 1/5
Dimensione prima del resume: 2889875456 byte, 2.69 GiB

+ curl https://chatgpt.com/backend-api/estuary/content?[REDACTED_QUERY] [resume, config temporaneo, cookie redatti] -o chatgpt-export.zip

HTTP resume: 206
Byte scaricati nel resume: 1330561245
Dimensione dopo resume: 4220436701 byte, 3.93 GiB

Verifica ZIP dopo resume...
ZIP valido secondo unzip.
Firme finali ZIP: EOCD normale=sì, EOCD ZIP64=sì, ZIP64 locator=sì

Report scritto in: report-export-chatgpt.txt

ZIP valido.

+ unzip -q -o chatgpt-export.zip -d chatgpt-export-estratto

Export estratto in: chatgpt-export-estratto
File HTML principale: chatgpt-export-estratto/chat.html

RIEPILOGO
------------------------------------------------------------
- Download iniziale: HTTP 200, 2889875456 byte, 2.69 GiB
- Dimensione dopo download iniziale: 2889875456 byte, 2.69 GiB
- Resume 1: HTTP 206, +1330561245 byte, 1.24 GiB
  Dimensione dopo resume 1: 4220436701 byte, 3.93 GiB
- Dimensione finale: 4220436701 byte, 3.93 GiB
- ZIP: valido
- EOCD normale: trovata a offset 4220436679
- EOCD ZIP64: trovata a offset 4220436603
- ZIP64 locator: trovata a offset 4220436659
- Estratto in: chatgpt-export-estratto
- Report: report-export-chatgpt.txt

Nota sicurezza: elimina chrome-curl.txt e cookies-minimi.txt, oppure esegui: ./chatgpt_export_resumer.py --cleanup
Dopo l'uso valuta logout e login da ChatGPT.
```

In questo caso, il download iniziale si era interrotto a `2.69 GiB`. Lo ZIP iniziava correttamente, ma non conteneva i record finali della directory centrale. Lo script ha rilevato l'assenza dei record EOCD e ZIP64, ha ripreso il download con `curl -C -`, ha ricevuto una risposta `HTTP 206 Partial Content`, ha scaricato gli `1.24 GiB` mancanti e ha prodotto un archivio valido di `3.93 GiB`.

## Cosa è successo tecnicamente?

La risposta iniziale era corretta:

```text
HTTP_CODE: 200
CONTENT_TYPE: application/octet-stream
```

Quindi il server aveva effettivamente restituito dati binari.

Tuttavia, il file locale era incompleto. Iniziava come uno ZIP, ma non conteneva i record di fine directory centrale (*end-of-central-directory*) necessari per leggere l'archivio.

Quando lo script ha eseguito `curl` in modalità resume:

```bash
curl -C -
```

il server ha risposto:

```text
HTTP_CODE: 206
```

Il codice `206` significa **Partial Content**, cioè contenuto parziale. In questo caso, il server ha inviato la parte finale mancante e lo ZIP è diventato valido.

## Risoluzione dei problemi

### `HTTP_CODE: 403`

Di solito significa che la richiesta non è autenticata oppure viene reindirizzata verso una pagina di login o di verifica (*challenge*).

Usa gli strumenti per sviluppatori di Chrome e copia la richiesta autenticata con:

```text
Copy > Copy as cURL
```

### `Warning: skipped provided cookie, the cookie header would go over 8200 bytes`

Chrome ha copiato troppi cookie.

Lo script elimina molti cookie non necessari, soprattutto quelli che iniziano con `conv_key_*`, e conserva soltanto quelli normalmente utili per l'autenticazione e il download.

### `End-of-central-directory signature not found`

Probabilmente lo ZIP è incompleto.

Esegui nuovamente lo script senza `--force`, oppure lascia che tenti automaticamente il resume.

### Lo ZIP esiste già

Lo script verifica prima lo ZIP già presente.

Se è valido, non tenta un nuovo download.

Se è incompleto, prova a riprenderlo.

Per ricominciare da zero:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --force
```

### Il link è scaduto

I link per scaricare gli export di ChatGPT scadono dopo 24 ore.

Richiedi una nuova esportazione e ripeti la procedura.

## Download e codice sorgente

- [Repository GitHub e segnalazione problemi](https://github.com/levysoft/chatgpt-export-resumer)
- [Script Python](chatgpt_export_resumer.py)
- [Documentazione in inglese](README.md)
- [Sito Levysoft](https://www.levysoft.it/)

Per utilizzare lo strumento, clona la repository seguendo le indicazioni nella sezione **Installazione**. Non è necessario scaricare una release confezionata.

## Licenza e riconoscimenti

Distribuito con **licenza MIT**. Vedi [LICENSE](LICENSE).

Autore: **Antonio Troise (Levysoft)**  
Sito del progetto: https://www.levysoft.it/  
Sito dell'autore: https://www.levysoft.it/  
GitHub: https://github.com/levysoft/

Il progetto nasce dall'analisi di un download incompleto di un export ChatGPT di grandi dimensioni. Utilizza la funzionalità standard di ripresa di `curl` e la libreria standard di Python.
