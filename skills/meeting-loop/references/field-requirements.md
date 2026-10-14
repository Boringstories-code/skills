# Field requirements — what regulated professions actually demand

Research pass 2026-08-23 (Perplexity rung 2 + corroboration). Purpose: ship defaults that are lawful and
usable in the fields people actually record in, instead of inventing personas. Findings here drive
`profile.schema.json` and the setup grill's defaults.

**Status: complete — clinical/legal, regulated institutions, and cross-cutting corporate.**

## The structural advantage worth knowing before anything else

**This skill is file-based, not a bot.** It processes a recording someone already made. It does not
auto-join calendar events, does not sit in meetings, and does not auto-email transcripts to invitees.

That matters more than any feature in it. Auto-join is the mechanism behind the Otter class actions, the
closed-session criminal exposure in Texas, the IEP and IRB failure modes, and the enterprise bot-blocking
now shipping in Microsoft and Zoom. The single most dangerous default in this product category is one we
structurally cannot have. Do not add it.

Named failure patterns from the litigation, all real, all avoided by being file-based: bot auto-joins
every calendar entry · recording continues after the meeting ends · transcripts auto-emailed to all
invitees including no-shows · host stops recording but transcription keeps running · vendor default
deletion destroys a record under legal hold.

> Not legal advice. Every entry names its source; jurisdictional variation is flagged. Where a source
> was thin, it says so — an unsourced compliance claim is worse than an admitted gap.

## The finding that changes our engine

**Acoustic diarization generates a voiceprint, and a voiceprint is a regulated biometric identifier.**
`diarize_no_hf.py` (Resemblyzer) and `diarize_single_mic.py` (pyannote) both compute speaker embeddings —
that is voiceprint extraction. Illinois BIPA governs it, and BIPA voiceprint claims are live in
*In re Otter.AI Privacy Litigation*, No. 5:25-cv-06911 (N.D. Cal.), which consolidates *Brewer*, *Walker*,
*Theus*, and *Winston* against an AI notetaker.

`diarize_two_mic.py` compares energy across two recorders. It builds no embedding, so it generates no
biometric. It was already the most accurate method in the skill — measured 57.4% vs a 71.3% baseline for
the acoustic path on real audio — and it now turns out to be the legally safer one too.

**Consequence for the design:** `environment.diarizer_preference` is not a pure quality knob. In a
BIPA-style jurisdiction, or any install with unconsented third parties, acoustic diarization needs its
own consent basis. Two-mic and text attribution do not.

**Second engine-level finding: "we don't store the audio" is not a defense.** Under CIPA §631(a) and
*Ribas v. Clark*, reading or learning the contents is enough — capture is the violation, not retention.
So the consent gate must fire at **capture**, not at storage. Step 5a is correctly placed; deleting audio
afterward does not cure a recording that shouldn't have happened.

**Third: hallucination is the documented failure mode, not a hypothetical.** Koenecke et al., *Careless
Whisper* (ACM FAccT 2024): ~1–1.4% of Whisper transcriptions contained fully invented sentences, ~38–40%
of those carrying explicit harm — invented medications, inserted race, violent content — **worst during
silences**, which are common in aphasia and in any recording with pauses. Whisper is our ASR. Caveat: the
study used AphasiaBank, not clinical audio, and documented no patient harm. This validates the
never-distill-raw invariant and adds a new one below.

**The verifiability tension, unresolved on purpose.** Deleting raw audio reduces liability (it is
discoverable, subpoenable, and contains what the note omits). Keeping it is what lets anyone check
whether the ASR invented a line. Nabla was criticized for deleting audio precisely because it made
transcripts unverifiable. There is no default that is right for every field — which is why retention is
a profile field and not a constant.

## Cross-cutting: consent is a matrix, not a list

**Do not hard-code a flat all-party state list — the medium is a second dimension.**

- **Clear all-party (10):** CA (Penal §632), DE, FL, IL (720 ILCS 5/14-2), MD, MA, MT, NH, PA, WA.
- **Hybrid, depends on medium:** Connecticut — telephone all-party under civil §52-570d, criminal
  §53a-189 differs. Nevada — all-party for phone/electronic, one-party in person. **Oregon (ORS 165.540)
  is the reverse: all-party in-person, one-party by phone.** Hawaii — one-party unless in a private place.
- **Disputed / absent:** Michigan's statute text reads all-party but federal courts have applied a
  participant exception; unresolved. **Vermont has no wiretap statute at all.**
- Any chart claiming "11 states" or "13 states" is collapsing the hybrids. Ours must not.

Federal baseline is one-party (18 U.S.C. §2511(2)(d)), overridden where state law is stricter. In an
all-party state consent is needed from **everyone captured** — family, interpreter, trainees, the person
who walks in mid-meeting.

**Multi-state calls have no controlling rule.** Courts split between most-significant-relationship,
place-of-interception, and forum law. Following the most protective participant's state is prudence, not
doctrine. **Product consequence: consent config keys off every participant's location, not the host's.**

**In-person vs phone vs video are legally different acts.** In-person usually turns on a fact-specific
"confidential communication" test. Phone statutes are often stricter and skip that test. Video is several
acts at once — audio, video capture, and screen/chat content — and audio consent does not dispose of the
video or biometric questions.

**A banner is notice, not consent.** It fails where it appears post-capture, doesn't name the external
vendor, isn't visible to dial-in participants, or where affirmative consent is required.

---

## Healthcare / medical

- **Consent.** HIPAA does not require patient consent to record for treatment or operations; wiretap law
  does. CA AB 3030 (Health & Safety Code §1339.75, eff. 1/1/2025): GenAI-generated patient clinical
  communications need a disclaimer plus human-contact instructions — **exempt when a licensed provider
  reviews first**. EU/UK: health data is GDPR Art. 9 special category; consent is one possible basis, not
  automatically the correct one.
- **Retention.** The signed note follows state medical-record schedules (commonly ~7–10 years for adults,
  longer for minors). No federal rule makes raw audio part of the record. **Litigation hold overrides any
  deletion schedule.**
- **Egress.** Cloud is fine *with a BAA*, encryption in transit and at rest, access logging, no-secondary-
  training terms, subprocessor disclosure. HIPAA imposes no US data-residency rule and does not require
  on-device processing.
- **Artifact.** Must support the billed E/M level with the clinician's actual decision-making and a
  truthful attestation of review. Must not contain fabricated findings or unsupported diagnoses.
- **Dealbreaker.** No BAA. Encryption doesn't cure it; later deletion doesn't cure it.
- **Practice.** Abridge, Nuance DAX Copilot, Suki, Ambience, Freed, Heidi.

## Mental health / psychotherapy

- **Consent.** Above, plus APA Ethics Code requires permission before recording voice or image; ACA and
  NASW require the same across any medium. A boilerplate intake clause is likely inadequate for AI — it
  discloses neither the vendor, the cloud egress, nor training use. **Group therapy is effectively
  disqualifying** for a general tool: every participant must consent, a refuser needs a real non-recorded
  option, and one file holds multiple patients' PHI.
- **Retention.** APA guidance: 7 years post-last-service for adults, 3 years past majority for minors,
  whichever is later — guidance, not federal mandate; state boards control. Raw audio: delete fast. It is
  voice-biometric, unredactable, and richer than the note.
- **Egress.** BAA plus overlays: **42 CFR Part 2** (SUD treatment; 2024 final rule, compliance
  2026-02-16) creates SUD counseling notes needing separate consent and restricting use in legal
  proceedings. Also CA CMIA, Illinois MHDDCA, NY. No rule mandates local processing — but for Part 2
  audio, group sessions, or a vendor that won't disclose subprocessors, local is often the only
  defensible architecture.
- **Artifact — the hard structural requirement.** Under 45 CFR 164.501, psychotherapy notes are the
  clinician's session-analysis notes **kept separate from the record**, excluding medications, start/stop
  times, modalities, test results, diagnosis, functional status, symptoms, and prognosis. **A single AI
  output blending process observation with diagnosis and billing is not a psychotherapy note, and merging
  it into the chart destroys the §164.508 authorization protection.** The tool must emit two segregated
  artifacts or none.
- **Dealbreaker.** A tool that emits one merged note. Second: no contractual bar on training or secondary
  use.
- **Practice.** Blueprint, Mentalyc, Upheal, SimplePractice AI, Eleos. No substantiated product-specific
  enforcement action found against any of them.

## Legal practice

- **Consent.** ABA Formal Op. **01-422** (2001) withdrew Op. 337: lawful secret recording is not per se
  unethical, but recording in violation of an all-party statute may violate Rules 8.4 and 4.4, and a
  lawyer may never falsely deny recording. The Committee split on recording one's own client and called
  it "at the least, inadvisable." CO and SC rejected 01-422; AZ, ID, IN, IA, KS, KY never withdrew
  contrary opinions. Depositions: FRCP 30 governs the official record — a court reporter's authorization
  does not license a side AI recording.
- **Retention.** No single national period. Recordings containing client instructions or facts likely
  become client-file material surrenderable on request; "temporary buffer" labeling won't shield
  substantive content.
- **Egress / privilege.** ABA Formal Op. **512** (2024) applies Rule 1.6 to GenAI: reasonable efforts to
  prevent unauthorized disclosure, plus competence, supervision, and client communication. Florida Op.
  24-1 and NYC Bar Formal Op. 2024-5 track the same analysis. Vendor use is **not** automatic waiver
  under 1.6(c) — but a consumer tool with shared-model training, indefinite retention, and vague deletion
  fails the standard. Self-hosting reduces but does not eliminate the duty.
- **Artifact.** Work product protects mental impressions prepared *because of* anticipated litigation —
  not every lawyer-made document, and never the underlying facts. An unreviewed AI summary is
  discoverable, can convert hedged statements into apparent admissions, and misattributes speakers.
  Litigation hold must reach audio, transcripts, prompts, summaries, and vendor-side copies.
- **Dealbreaker.** No enforceable no-training, deletion, or legal-hold guarantee on privileged audio.
- **Practice.** CoCounsel, Harvey, Lexis+ AI, Clio Duo; Otter and Read AI on the general side. Live
  controversies: *Mata v. Avianca* and successors (sanctions for hallucinated citations), and the Otter
  consolidation above. No merits rulings yet.

## Insurance (claims / recorded statements)

- **Consent.** Same wiretap map. NAIC's Unfair Claims Settlement Practices Act is a *model*, not law —
  the enacted state version controls, and it addresses fair investigation rather than recording consent.
  An undisclosed recording still feeds bad-faith theories. Claimants may generally refuse. **Voice
  biometrics is a separate trap** — speaker-ID features trigger BIPA and similar laws.
- **Retention.** No universal figure; ~5–7 years post-closure is a common carrier baseline from state
  record-retention rules, limitations periods, and market-conduct exams — **verify per state; no single
  controlling federal citation found.** Retain the *original unaltered audio* where the statement is
  material; a transcript is a derivative and can be impeached.
- **Egress.** GLBA Safeguards (insurers are financial institutions), NAIC Insurance Data Security Model
  Law in adopting states, NYDFS 23 NYCRR Part 500 for covered NY entities — all impose written infosec
  programs and third-party service-provider oversight.
- **Artifact.** Must record date, participants, whether recorded, the exact consent method, material
  facts, contradictions, and the objective basis for any SIU referral, with facts separated from opinion.
  Must not characterize ("fraud", "liar") or state speculation as fact. Ordinary adjusting files are
  generally **not privileged**; labeling doesn't create privilege.
- **Dealbreaker.** **No reproducibility.** Claim notes, prompts, and AI summaries all become bad-faith
  discovery — a tool that can't show what the model generated, who edited it, and from which audio is
  unusable.
- **Practice.** Verint/Nuance, Clearspeed, EXL, CCC, Sapiens, Five Sigma. **NAIC Model Bulletin on Use of
  AI by Insurers** (adopted Dec 2023, ~24 state adoptions) expects a written AI governance program,
  validation, monitoring, and record retention. Colorado SB21-169 governs external data and algorithms
  for unfair discrimination. **California SB 1120 is health-plan utilization review only — do not cite it
  as a general P&C claims rule.** *Cigna PXDX* and *UnitedHealth nH Predict* are allegations, not
  findings.

## Financial services (broker-dealer / RIA / banking)

- **Consent.** US one-party baseline, all-party in CA/FL/PA/IL/WA. EU/UK is the opposite posture: MiFID II
  Art. 16(7) **mandates** recording calls "intended to result in a transaction" and requires client
  *notification*, not consent; FCA COBS 11.8 mirrors it. Firms must block unrecorded channels.
- **Retention.** SEC Rule 17a-4(b)(4): **3 years**, first 2 easily accessible. FINRA 4511: **6 years**.
  Advisers Act 204-2(a)(7) parallel. MiFID II: **5 years**, 7 on demand. No mandatory maximum — GDPR Art.
  17 and CCPA erasure both carve out legal-obligation retention, so deletion requests lose.
- **Egress.** 17a-4(f) as amended 2022: either WORM **or** the audit-trail alternative — time-stamped
  record of every modification and deletion, actor identity, ability to recreate the original — plus a
  **designated third party undertaking** giving the SEC direct access. Cloud AI is possible only if the
  original audio is preserved pre-processing, the vendor can't delete, rewrite, or train on it, and a D3P
  letter exists. A consumer AI account with admin delete rights fails outright.
- **Artifact.** The rule says *originals of communications*. A summary is never a substitute.
- **Dealbreaker.** Any tool where the vendor or user can delete or silently edit the recording with no
  original retained.
- **Enforcement.** Off-channel sweep since Dec 2021: **100+ firms, $2.2bn+ in SEC penalties.** No action
  to date names an AI notetaker — but the theory is identical: an unarchived channel.

## Government / public sector

- **Consent.** Open meetings are public; no individual consent. Most states require **minutes, not
  recordings**. Texas is the instructive outlier: Gov't Code §551.021 requires minutes *or* a recording;
  §551.103 requires a certified agenda *or* recording of each closed meeting, and participating in a
  closed meeting knowing neither is being made is a **Class C misdemeanor**.
- **Retention.** §551.104: closed-session records preserved **≥2 years**, longer under litigation.
  Minutes typically permanent. Federal agencies follow the Federal Records Act and NARA schedules.
- **Egress.** Recordings, transcripts, AI summaries, bot logs, and prompts are **all potentially public
  records** — vendor possession doesn't shield them. FedRAMP/StateRAMP authorization covers a *service
  boundary*, and AI transcription add-ons are frequently outside it.
- **Artifact.** Minutes are a **summary of actions**, not verbatim — the subject of each deliberation plus
  every vote and decision. AI output is a **draft**; the clerk verifies and the body adopts. Where statute
  requires the clerk to certify, an AI artifact cannot be the official record.
- **Dealbreaker.** Texas §551.104(c): disclosing a closed-session recording without a court order is a
  **Class B misdemeanor**. Storing executive-session audio on a vendor cloud is criminal exposure, not a
  policy problem.

## Education (K-12 and higher ed)

- **Consent.** IDEA creates **no** federal right to record IEP meetings; state law governs. CA Ed Code
  §56341.1(g)(1) requires **24 hours' notice** by either party. Elsewhere it may be prohibited absent
  district agreement.
- **Retention.** A recording is an **education record** if directly related to an identifiable student and
  maintained by the school *or a party acting for it, including a vendor*. IDEA 34 CFR §300.624 is a
  **mandatory destruction duty** — when PII is no longer needed, notify parents and destroy on request.
- **Egress.** Permissible only via the school-official exception, 34 CFR §99.31(a)(1): the vendor must be
  under the district's **direct control**, use data only for the authorized purpose, and not redisclose.
  Stacked state law: CA SOPIPA / Ed Code §49073.1, NY Ed Law §2-d, IL SOPPA. **A staffer's personal
  Otter or Fireflies account is not covered by the exception** — that is the common real-world violation.
- **Artifact.** Never verbatim. The legally operative documents are the **IEP** and **prior written
  notice**, which must state the action proposed or refused, the reasons, records relied on, and options
  rejected. A transcript amends nothing and substitutes for neither.
- **Dealbreaker.** Vendor training on student audio — breaks §99.31(a)(1) direct control and violates
  SOPPA, 2-d, and SOPIPA simultaneously.

## Academic / clinical research

- **Consent.** 45 CFR §46.116 elements, plus IRBs require recording disclosed specifically — who hears it,
  transcription and AI processing, storage, deletion — with a **separate opt-in** and the ability to
  participate unrecorded. Recording usually **defeats** the §46.104(d)(2) interview exemption, because
  voice makes identity readily ascertainable.
- **Retention.** §46.115(b): IRB *records* ≥3 years post-completion. FDA: 21 CFR 312.62 and 812.140.
  **The self-imposed maximum binds** — if the consent form promises destruction after transcription, you
  must destroy, including vendor copies, caches, and backups.
- **Egress.** PHI plus a transcription vendor makes a business associate; **BAA required before
  disclosure**, and the IRB-approved data flow must name the vendor. Voice is not de-identified by
  removing names — Safe Harbor's 18 identifiers include biometric identifiers. Certificates of
  Confidentiality bar compelled disclosure. Increasingly the answer here is **local Whisper**.
- **Artifact.** For trials: ALCOA+ and 21 CFR Part 11 — validated system, access controls, computer-
  generated audit trail, original preserved with correction history. **An AI summary is a derived product,
  not source data.**
- **Dealbreaker.** A transcript that can be silently overwritten with no audit trail and no traceable link
  back to source audio.

## GDPR / UK — the parts that bite this design

- **Lawful basis.** Legitimate interests is generally more defensible than consent for routine notes;
  **consent in employment is frequently invalid** (power imbalance, Art. 7 / §26(2) BDSG). Document a
  three-part assessment; **recording off by default**. ICO guidance says workplace audio recording needs
  specific justification and should be rare.
- **Special category drift.** Meetings wander into health, union membership, religion. Legitimate
  interests alone doesn't cover Art. 9 data. The ICO's own Teams DPIA concedes this.
- **Transcripts are personal data — and so are summaries, speaker labels, embeddings, prompts, and audit
  logs.** Art. 13 covers attendees; **Art. 14 covers people merely *mentioned* who never attended.**
- **DSAR.** The requester gets their own personal data, not automatically the raw file. Redact third
  parties rather than blanket-refusing. **Misattributed speech is inaccurate personal data** and creates
  rectification exposure — which is the legal form of the diarization accuracy problem.
- **Erasure.** Not absolute, but deletion must reach **derived copies**: backups, search indexes, caches,
  embeddings, and anything distilled downstream. Architect raw audio, working transcript, approved
  output, and derived artifacts as **separately deletable**.
- **Retention benchmarks** (examples, not safe harbors): ICO's own Copilot notice deletes Teams
  recordings and transcripts at 21 days, prompts and responses at 7. Blanket multi-year retention needs
  justification. A DPIA is effectively mandatory for workplace-wide deployment.

## EU AI Act

- A transcription-plus-summary tool **is** an AI system but is normally **minimal risk**. It is not
  high-risk merely for containing an LLM.
- **Art. 5(1)(f) emotion-recognition ban has been live since 2 Feb 2025** — inferring emotions in
  workplace or education contexts, medical and safety excepted. A confidence, sentiment, or coachability
  score inferred from **voice** likely falls inside the ban. Purely lexical sentiment from transcript text
  is arguably outside it — arguable, not settled. Art. 5(1)(g) separately bans biometric categorisation by
  sensitive traits.
- **Annex III point 4** bites when the tool scores, ranks, or recommends on hiring, promotion, discipline,
  or termination, or monitors worker performance. Neutral minutes with no scoring likely stay out.
- **Timeline, recently changed:** Art. 5 and AI literacy since 2 Feb 2025; GPAI 2 Aug 2025; **Art. 50
  transparency live 2 Aug 2026, not delayed**; Annex III high-risk **moved to 2 Dec 2027** by the Digital
  Omnibus, Regulation (EU) 2026/1744, in force 27 July 2026.

## Employee monitoring — Germany is the hard gate

- **§87(1) no. 6 BetrVG:** works council co-determination triggers on the *technical capability* to
  monitor, not employer intent (BAG 1 ABR 20/21, Office 365). A notetaker with speaker attribution or
  searchable transcripts almost certainly needs a **Betriebsvereinbarung** before rollout. **Employee
  consent does not substitute.**
- **§201 StGB is separate and criminal** — secretly recording the non-public spoken word, regardless of
  GDPR compliance.
- **France:** CSE consultation before go-live (L2312-38). **Netherlands:** works council **consent** under
  WOR Art. 27. Nordics vary by collective agreement.
- **An employee recording colleagues is its own risk** — potentially criminal in Germany and grounds for
  dismissal. The product should not make a covert personal bot easy to run inside a corporate meeting.

## HR / recruiting

- Illinois **AI Video Interview Act** (820 ILCS 42): pre-interview notice, an explanation of what the AI
  evaluates, and **affirmative consent**. NYC LL144 is not a recording law — it's a bias-audit and notice
  rule for automated employment decision tools; pure transcription is out of scope, but scoring or
  ranking candidates puts you in it.
- Illinois HB 3773 effective 1 Jan 2026. **Colorado SB 24-205 never took effect** — repealed and replaced
  by SB 26-189, signed 14 May 2026, effective **1 Jan 2027**.
- **Dealbreaker: creating voiceprints or emotion/personality scores.** BIPA class-action fuel in the US,
  prohibited under Art. 5(1)(f) in the EU.

## Sales, journalism, coaching

- **Sales.** Script to the strictest participant's state, before capture. CIPA §631 class actions reach
  vendors, not only the recording company. A recording can be lawful and the LLM transfer still breach the
  customer's own MSA/DPA.
- **Journalism.** **Source protection is the whole game.** The Privacy Protection Act restricts government
  *searches* — it is not a privilege against subpoenas or civil discovery, and shield laws generally don't
  immunize your vendor. Cloud AI adds custodians subject to subpoena. A transcript re-identifies a source
  through timing, phrasing, and location even with the name stripped. **Anonymous-source interviews: local
  only, or don't ship to newsrooms.**
- **Coaching.** ICF requires consent before recording and explaining the *limits* of confidentiality.
  **Coaching is not privileged** — records are subpoenable. The specific trap is sponsor-paid coaching
  where the employer's tenant hosts the transcript: the client believes it's private and the sponsor can
  read it. The tool must make that custody boundary explicit.

## Two findings that hit channels we already built

**1. Channel B (person-enricher) is the most legally exposed thing in the skill.** It extracts, about
*other people*, "temperament, what they care about, how they decide" and writes it to a durable dossier.
Three separate problems the persona test only half-saw:

- **GDPR Art. 14 covers people merely mentioned who never attended.** Channel B profiles third parties who
  were never in the room and never got notice.
- **EU AI Act Art. 5(1)(f)**, live since Feb 2025, prohibits inferring emotions in workplace contexts.
  "Temperament" and "how they decide" inferred from a recording is arguably exactly that. Lexical
  inference from text is a better argument than voice-derived inference — but it is an argument, not a
  safe harbor.
- **Germany §87(1) no. 6 BetrVG**: speaker attribution plus searchable transcripts already triggers works
  council co-determination on technical capability alone. Dossiers on colleagues make it worse, and
  employee consent does not cure it.

The persona test called Channel B "an HR exposure." The research says it is sharper than that. Default
**off** for company installs stands, and EU installs should default it off regardless of `install.kind`.

**2. Distillation creates derived copies that erasure must reach.** GDPR erasure must reach backups,
indexes, caches, **embeddings**, and anything distilled downstream. Our L2 tier wicks concepts into a
wiki, deliberately dedupes and merges them into pages, and cites back. That is a derived copy by design.
Deleting a meeting note does not delete the concept page it fed. Raw audio, working transcript, approved
output, and derived artifacts must be **separately deletable**, and `cite_back` is what makes that
possible — it's not a nicety, it's the deletion path.

Related: **misattributed speech is inaccurate personal data** under GDPR, with rectification exposure.
That is the legal form of the diarization-accuracy problem we already measured. The existing rule — score
it, throw it away when it loses, leave turns as `SPEAKER:` — is the legally correct behavior too.

## Thin sources (flagged, not papered over)

Per-state insurance retention periods; product-specific enforcement against any named clinical or
behavioral-health scribe vendor; whether specific ambient-scribe vendors actually delete audio (every such
claim is a contract term, not a verified fact). No SEC/FINRA enforcement action names an AI notetaker; no
FERPA action names one; no state AG opinion found on AI-generated minutes. The Michigan participant
exception; the lexical-vs-voice sentiment line under Art. 5(1)(f); *Cruz v. Fireflies.AI* (single source,
unverified); a reported "April 2026 federal stay" on state AI laws (single law-firm source — would change
the Colorado picture materially, verify before relying). **The regulatory theories are clearly
applicable, but nobody has been fined specifically for this yet — anyone claiming settled precedent is
selling something.**

---

## Six rules that hold across every field

1. **Never let the AI summary be the record.** All eight fields treat it as a derivative. Capture and
   preserve the original first, always.
2. **No auto-join, ever.** Being file-based is the design's biggest compliance asset. Don't spend it.
3. **Egress is a per-profile switch, not a setting.** Financial and research need a local-only path,
   education needs contractual no-training, government needs a documented service boundary, journalism
   needs local-only for anonymous sources.
4. **Two retention clocks in tension.** Minimums (17a-4, FINRA 4511, MiFID II, TOMA §551.104) versus
   mandatory destruction duties (IDEA §300.624, consent-form promises, GDPR minimization). **Legal hold
   overrides automatic deletion in both directions.**
5. **Audit trail is the entry ticket.** WORM or the 17a-4(f) alternative gets you into financial
   services and coincidentally satisfies Part 11 for research and reproducibility for insurance.
6. **Verbatim versus summary splits by field.** Government minutes are *required* to be a summary of
   actions; finance and clinical research require the preserved original; education requires neither
   because the IEP and prior written notice are what count.

## Design implications — what the research forces into the schema

| Finding | Schema/step change |
|---|---|
| Voiceprints are biometrics (BIPA) | `diarizer_preference` needs a biometric flag; acoustic paths need their own consent basis |
| Capture, not storage, is the violation | Consent gate stays at Step 5a; never justify by deletion |
| Consent is a matrix, not a list | Consent config keys off **every participant's** location and the medium |
| Psychotherapy notes must be segregated | `output_shape` must support **two artifacts with different governance** — no such concept today |
| BAA/DPA gates cloud egress | `llm.egress_allowed` boolean is insufficient — needs `processor_contract: baa \| dpa \| none` |
| Legal hold overrides deletion | `retention` needs a `legal_hold` state that suspends the sweep |
| Reproducibility is a dealbreaker | Provenance: which audio, which model, what was edited, who reviewed |
| Unreviewed AI output is discoverable | `review_required` before an artifact counts as final |
| Original must be preserved pre-processing | An `originals` policy distinct from `retention` |
| Erasure must reach derived copies | Deletion path from a meeting through its distilled concepts — `cite_back` is that path |
| Emotion inference is banned in EU workplaces | Channel B defaults off for EU installs regardless of `install.kind` |
| Works council co-determination (DE/FR/NL) | Company installs in those jurisdictions need a pre-rollout gate, not a consent checkbox |
| Group sessions hold multiple people's data | Type-level refuse flag, not a runtime judgment call |
