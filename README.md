# Mapping van Rijkswaterstaat eigen formaat naar Internationale Scheldecommissie.

## Doel

De voorbeeldbestanden zijn handgemaakte mappings van RWS (donar) naar ISC. In dit project gaan we de mappings automatiseren middels vertaaltabellen. 

## Gegevensbestanden

Het Zip bestand bevat de DONAR export met gegevens van chemische waterkwaliteit.
Het Transfert de donnees Excel bestand bevat het gevraagde format.
Het Oct_2025_NL bestand bevat het uiteindelijk geleverde bestand aan ISC

## Plan voor het maken van de mappings

-	De mappings voor parameter zijn ons inziens te maken door:
  +	De Donar codes te matchen met de AQUO parametertabel
  +	De CAS codes (AQUO) te matchen met de gevraagde CAS codes. 
  + Mocht niet alle donarcodes matchen met aquo dan kunnen we nog kijken of we dat via de WRD parameter tabel kunnen doen. Anders met de hand
  -bekijken met PAR kolom ipv PAROMS
  +	Bijzonderheden, zoals opgeloste fractie, halen we uit hdhcod 
    +	als er “nf” in voorkomt, is het opgeloste fractie
    +	als er “pg” in voorkomt pariculair gebonden (wordt niet gerapporteerd)
    +	De rest is de totale fractie
-	Locaties mappen door op patronen te matchen met loccod of locoms. Bijv “Vlissingen” moet gematcht worden met “Vlissingen Boei SSVH”. 
-	Kwaliteitscode staat in Donar (aanname: alles <= 50 is goed, alles daarboven hiaatwaarde)
-	Kwantificeringsgrens staat in Donar tabel
-	!Eenheden vergelijken met gevraagde eenheid. Omrekeningsfactor bepalen wanneer nodig.
- berekening daggemiddelden (ISC heeft alleen datum, geen datumtijd)

