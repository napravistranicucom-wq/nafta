# Pokretanje: waitlista + Instantly kampanja

## A. Waitlista na usecrewly.com (ti, ~30 min, ~10 $/god)
1. **Domena:** na Cloudflareu (dash.cloudflare.com → Domain Registration → Register) kupi `usecrewly.com`.
2. **Loops** (loops.so, besplatno do 1.000 kontakata):
   - Forms → Create form → kopiraj **form endpoint** (`https://app.loops.so/api/newsletter-form/...`).
   - U Audience → Contact properties dodaj: `company`, `techs`, `software`, `pain`, `phone`, `sms_consent`, `referral_code`, `referred_by`.
3. Pošalji mi Loops endpoint, a ja ga upišem u `site/index.html` (`FORM_ENDPOINT`). Može i sam.
4. **Cloudflare Pages:** Workers & Pages → Create → Pages → **Upload assets** → povuci mapu `site/` → Custom domains → `usecrewly.com`.
5. Probaj prijavu na stranici i provjeri da je stigla u Loops.

## B. Instantly (ti, pa ja)
1. **Instantly** (instantly.ai), plan Growth ~37 $/mj.
2. **Inboxi za slanje:** Instantly → Email Accounts → **Done-for-you**. Uzmi 2–3 domene koje liče na brend (npr. `getcrewly.com`, `trycrewly.com`; provjeri jesu li slobodne) s 2 inboxa po domeni. **Nikad ne šalji s `usecrewly.com`.**
3. Uključi **warmup** na svim inboxima i čekaj **2 tjedna** prije slanja.
4. U `outreach/sequence.json` zamijeni `POSTAL_ADDRESS` stvarnom poštanskom adresom. To traži američki zakon CAN-SPAM. Može i virtualni poštanski sandučić (npr. iPostal1, ~10 $/mj).
5. Instantly → Settings → Integrations → **API Keys** → napravi ključ (API v2). Reci mi kad je spreman: dobit ćeš sigurnu formu u koju ga upišeš, a ja ga ne vidim.
6. **Ja** pokrenem `outreach/instantly_setup.py`. Skripta napravi kampanju (pauziranu) s A/B porukama i rasporedom (uto–čet, 7:00–10:30 Central) i ubaci 497 leadova iz SAD-a.
7. **Ti** u Instantlyju pregledaš kampanju i uključiš **Unsubscribe link** u Options. Prije slanja provjeri adrese (Instantly → Verify ili NeverBounce), pa klikneš **Resume**.

## Brojke
- 6 inboxa × 30 mailova dnevno daje ~180 mailova dnevno, a prvi val (497) prođe za ~3 dana slanja.
- Cilj: >40 % otvaranja i >3 % odgovora. Na svaki odgovor odgovori unutar sat vremena.
- Nakon ~100 poslanih vidi koja verzija prve poruke (A ili B) ima više odgovora, pa ostavi samo nju.
