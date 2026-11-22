# Crewly waitlist stranica

`index.html` je cijela stranica u jednoj datoteci, spremna za objavu na **usecrewly.com**.

## Objava (besplatno)
1. Kupi domenu `usecrewly.com` (Cloudflare ili Namecheap, ~10 $/god).
2. **Cloudflare Pages** ili **Netlify**: "Deploy manually", povuci mapu `site/` i spoji domenu.

## Da se prijave spremaju
U `index.html` pronađi `var FORM_ENDPOINT = "";` i upiši jedno od ovoga:
- **Formspree** (formspree.io, besplatno do 50 prijava mjesečno): `https://formspree.io/f/XXXX`
- **Loops** (loops.so, besplatno do 1.000 kontakata; prijave odmah ulaze u e-mail niz za waitlistu): `https://app.loops.so/api/newsletter-form/XXXX`

Forma šalje: name, email, company, techs, software, pain, phone, sms_consent, referral_code, referred_by, source.

## Referral
Nakon prijave svatko dobije link `usecrewly.com/?ref=KOD`. Kad netko preko njega dođe, njegova prijava ima `referred_by=KOD`. Tako vidiš tko je koga doveo.

## Cijene na stranici
Pola cijene Housecall Pro-a (službeni cjenik, studeni 2026.):
Basic 39 $ (29 $ godišnje), Essentials 94 $ (74 $), Max 164 $ (149 $), dodatni korisnik 17 $.
