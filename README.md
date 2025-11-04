
# Implementare Switch

Acest proiect implementează un Switch virtual în Python, care include funcționalități de bază ale **Spanning Tree Protocol (STP)** și **VLAN**. Proiectul este conceput să funcționeze în medii de rețea simulate pentru a ilustra cum ar putea funcționa STP și VLAN în practică.

## Descrierea Generală

Acest switch virtual urmărește urmatoarele scopuri:
1. **Prevenirea buclelor în rețea** prin Spanning Tree Protocol (STP), care permite selectarea unui **root bridge** și configurarea corectă a porturilor. Astfel se creaza un arbore minim de acoperire ce permite transmiterea pachetelor eficient.
2. **Izolează traficul între VLAN-uri** folosind tagging VLAN pentru a permite transmiterea selectivă a pachetelor pe bază de ID-uri VLAN. In acest fel se poate segmenta traficul în rețea și se poate asigura securitatea și performanța.

## Cum funcționează

### STP (Spanning Tree Protocol)

Implementarea STP din acest proiect previne buclele în rețea, selectând un switch root (cu cel mai mic ID) și blocând porturile care ar crea bucle. Funcțiile cheie pentru implementarea STP includ:
- **`initialize_stp`**: Configurează starea inițială a porturilor și setează switch-ul ca root dacă este singurul din rețea.
- **`send_bdpu_every_sec`**: Trimite periodic mesaje BPDU de la root bridge pentru a menține topologia stabilă.
- **`process_bpdu`**: Procesează mesajele BPDU primite și actualizează starea porturilor pe baza lor, pentru a reflecta corect topologia rețelei.

### VLAN

Pentru segmentarea traficului în rețea, acest switch implementează VLAN (Virtual Local Area Networks), permițând fiecărui port să fie configurat ca **Trunk** (intre 2 switch-uri) sau **Access** (intre switch si host). VLAN-ul este marcat printr-un tag în frame-ul Ethernet, care este interpretat și transmis corespunzător:
- **`add_vlan_tag`** și **`remove_vlan_tag`**: Adaugă sau elimină tag-ul VLAN din pachetele Ethernet.
- **`manage_send_to_link`**: Gestionează trimiterea cadrelor între porturi, adăugând sau eliminând tag-urile VLAN, în funcție de tipul de port.

## Structura Codului

- **`parse_ethernet_header`**: Analizează header-ul Ethernet pentru a extrage informațiile despre adresele MAC, EtherType și VLAN ID.
- **`load_switch_config`**: Încarcă configurația switch-ului (inclusiv VLAN-urile și tipurile de porturi) dintr-un fișier intr-un obiect Switch.
- **`is_unicast`**: Verifică dacă o adresă MAC este unicast.
- **`main`**: Reprezintă funcția principală de rulare a programului, care ascultă traficul pe toate porturile, procesează mesajele BPDU și distribuie cadrele bazate pe MAC și VLAN.

## Fisiere de Configurare

Fiecare switch are un fișier de configurare, `configs/switch<ID>.cfg`, care definește:
- **Prioritatea** switch-ului pentru determinarea root bridge-ului.
- **Porturile și VLAN-urile** atribuite fiecărui port.
- **Tipul portului** care poate fi `Trunk` sau `Acces`

Exemplu de configurație (`switch1.cfg`)

## Mod de testare

Aveți la dispoziție un script de Python3, topo.py, pe care îl puteți rula pentru a realiza setupul de testare. Acesta trebuie rulat ca root:


```bash
sudo python3 checker/topo.py
```
Fiecare host e o simplă mașină Linux, din al cărei terminal puteți rula comenzi care generează trafic IP pentru a testa funcționalitatea routerului implementat. Vă recomandăm ping. Mai mult, din terminal putem rula Wireshark sau tcpdump pentru a face inspecția de pachete.

Pentru a compila codul vom folosi make.

```bash
make
```

Aceasta comanda va deschide 9 terminale, 6 pentru hosturi și 3 pentru switch-uri. Pe terminalul switch-ului veți rula

```bash
 make run_switch SWITCH_ID=X # X este 0,1 or 2
```
Pentru testarea automata a temei, rulati:

```bash
./checher/checker.sh
```
