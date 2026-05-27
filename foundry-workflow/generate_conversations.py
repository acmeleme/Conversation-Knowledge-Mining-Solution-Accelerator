"""
generate_conversations.py
─────────────────────────
Sends 500 diverse call-center questions to the Azure AI Foundry
CallCenterInsightWorkflow agent and persists results to JSON.

Usage:
    pip install -r requirements_volume.txt
    python generate_conversations.py
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from tqdm import tqdm

# ──────────────────────────────────────────────────────────────
# Configuration (edit here)
# ──────────────────────────────────────────────────────────────
ENDPOINT      = "https://aif-callcenter100.services.ai.azure.com/api/projects/proj-callcenter100"
AGENT_NAME    = "CallCenterInsightWorkflow"
MAX_CONCURRENT = 10
MAX_RETRIES   = 2
RESULTS_FILE  = Path(__file__).parent / "results" / "workflow_conversations.json"

# ──────────────────────────────────────────────────────────────
# Question bank – 500 unique call-center questions
# ──────────────────────────────────────────────────────────────
def build_question_bank() -> list[str]:
    # Seed templates per category
    billing = [
        "Why is my bill higher than usual this month?",
        "I was charged twice for the same service. Account #{acct}.",
        "How do I set up autopay for account #{acct}?",
        "Can I get a billing extension until {date}?",
        "What are the late payment fees on my plan?",
        "My bill shows ${amount} but I expected ${expected}.",
        "I need an itemised breakdown of my {month} invoice.",
        "Did you receive my payment of ${amount} on {date}?",
        "How do I dispute a charge of ${amount} on account #{acct}?",
        "Can I split my ${amount} balance into instalments?",
        "I'm on the {plan} plan – why was I billed for roaming?",
        "My promotional discount didn't appear on this bill.",
        "I cancelled last month but still received a bill for ${amount}.",
        "How do I get a paper bill instead of email?",
        "What happens if I don't pay my bill of ${amount} by {date}?",
        "Can you apply my ${amount} credit to next month's bill?",
        "I want to understand the 'Other Charges' section on my bill.",
        "Why was my autopay declined for ${amount}?",
        "I need my last 12 months of bills for account #{acct}.",
        "Is there a discount for paying ${amount} annually?",
    ]
    technical = [
        "My internet speed is {speed} Mbps but I pay for {plan_speed} Mbps.",
        "I can't make calls from my phone since {date}.",
        "How do I reset my {router_model} router?",
        "My phone won't connect to WiFi at {location}.",
        "I'm getting dropped calls every {minutes} minutes.",
        "My upload speed is terrible – only {speed} Mbps.",
        "The internet keeps disconnecting after {minutes} minutes of use.",
        "I can receive calls but can't dial out.",
        "My voicemail is full and I can't clear it.",
        "How do I enable WiFi calling on my {device}?",
        "My SIM card isn't detected after I switched phones.",
        "I'm getting 'SOS only' on my {device} in {location}.",
        "How do I turn off data roaming on my {device}?",
        "My router lights are all red after the power outage.",
        "Can't send MMS messages to {contact} since {date}.",
        "My {device} shows full bars but the internet doesn't work.",
        "How do I set up a guest WiFi network on my {router_model}?",
        "My internet cuts out every night around {time}.",
        "I'm getting echo on every call I make.",
        "How do I prioritise my gaming device on the router?",
    ]
    activation = [
        "How do I activate my new SIM for account #{acct}?",
        "When will my service be activated? I ordered {days} days ago.",
        "I want to add a new line for my son {name}.",
        "How do I port my number {phone} from another carrier?",
        "My eSIM isn't activating on my {device}.",
        "The activation code sent to {phone} is not working.",
        "I ordered a new plan on {date} – status update?",
        "How long does number porting normally take?",
        "I need a temporary number while my port completes.",
        "Can I activate my SIM in {location} even if I'm overseas?",
        "I got a replacement SIM but don't know how to swap it.",
        "The activation portal keeps showing an error.",
        "Can I choose my own phone number when activating?",
        "I'm activating a business line – what documents do I need?",
        "My prepaid SIM expired. Can it be reactivated?",
    ]
    account = [
        "I need to update my address to {address}.",
        "How do I change my plan from {old_plan} to {new_plan}?",
        "I want to cancel my service for account #{acct}.",
        "How do I add {name} as an authorised user?",
        "I forgot my account PIN. Can you reset it?",
        "How do I remove a line belonging to {name}?",
        "I want to upgrade my plan before my cycle resets on {date}.",
        "Can I transfer ownership of account #{acct} to {name}?",
        "My account shows an outstanding balance I already paid.",
        "How do I download my account details for tax purposes?",
        "I need a proof-of-service letter for account #{acct}.",
        "My security question answer isn't being accepted.",
        "How do I merge two accounts under one login?",
        "I want to set up parental controls for {name}'s line.",
        "Can I freeze my account while I'm overseas until {date}?",
        "How do I opt out of marketing communications?",
        "I changed my email and now I can't log in.",
        "What is my contract end date for account #{acct}?",
        "How do I get a copy of my original service agreement?",
        "I want to add international calling to my plan.",
    ]
    network = [
        "Is there an outage in {location} right now?",
        "Why don't I have coverage at my office in {location}?",
        "When will 5G be available in {location}?",
        "My signal drops to 2 bars inside my house.",
        "I had great coverage in {location} last month but nothing now.",
        "Is there planned maintenance affecting {location} on {date}?",
        "Can you check if a tower near {location} is down?",
        "My speeds drop to {speed} Mbps when I'm at {location}.",
        "Does your network support VoLTE in {location}?",
        "I rely on the network for remote work – when will coverage improve?",
        "My neighbour has your service and gets full bars – why not me?",
        "What's the estimated restoration time for the {location} outage?",
        "I travel to {location} weekly and always lose signal there.",
        "Does roaming work in {country}?",
        "My data slows down after {gb} GB – is there throttling?",
    ]
    cancellation = [
        "I want to cancel my account #{acct} effective {date}.",
        "What are the early termination fees for my {plan} plan?",
        "Can I cancel without a fee since service quality has been poor?",
        "I'm moving abroad and need to cancel my contract.",
        "How long does cancellation take to process?",
        "I cancelled but I'm still being charged for account #{acct}.",
        "Can I suspend instead of cancel while I'm travelling?",
        "What happens to my phone number when I cancel?",
        "I was promised no ETF when I signed up – please check.",
        "Can I cancel one line without cancelling the whole account?",
    ]
    upgrades = [
        "I want to upgrade to the {new_plan} plan.",
        "What deals are available for existing customers?",
        "Can I upgrade my device mid-contract?",
        "How do I trade in my {device} for a new one?",
        "I want to add unlimited data to my current plan.",
        "What's the difference between {plan_a} and {plan_b} plans?",
        "Is there a loyalty discount for customers on account #{acct} for {years} years?",
        "Can I upgrade one line without changing the others?",
        "When does my eligibility for upgrade kick in?",
        "I saw a promotion for ${amount} off a new phone – is it still valid?",
    ]

    # Substitution data pools
    accts    = [f"{100000 + i}" for i in range(500)]
    amounts  = ["45.99", "78.50", "120.00", "15.75", "200.00", "9.99", "55.20", "310.00"]
    expected = ["40.00", "60.00", "100.00", "10.00", "180.00", "9.00", "50.00", "300.00"]
    months   = ["January", "February", "March", "April", "May", "June",
                 "July", "August", "September", "October", "November", "December"]
    plans    = ["Basic", "Standard", "Premium", "Unlimited Pro", "Family Share", "Business Essentials"]
    old_plans = ["Basic 5GB", "Standard 20GB", "Legacy Unlimited"]
    new_plans = ["Premium Unlimited", "Business Pro", "Family Max", "5G Ultra"]
    locations = ["downtown Chicago", "Austin TX", "Brooklyn NY", "Miami FL",
                 "Seattle WA", "Phoenix AZ", "Denver CO", "Boston MA",
                 "San Jose CA", "Atlanta GA", "Portland OR", "Las Vegas NV"]
    devices   = ["iPhone 15", "Samsung Galaxy S24", "Pixel 8", "OnePlus 12",
                 "iPhone 14 Pro", "Galaxy A54", "Moto G Power"]
    routers   = ["ASUS RT-AX88U", "Netgear Nighthawk X6", "TP-Link Archer AX6000",
                 "Linksys Velop", "Eero Pro 6E"]
    names     = ["James", "Maria", "Carlos", "Sarah", "Ahmed", "Priya",
                 "David", "Lisa", "Michael", "Emma", "Robert", "Olivia"]
    speeds    = ["2", "5", "8", "12", "15", "25", "50"]
    plan_speeds = ["100", "200", "500", "1000"]
    minutes_vals = ["5", "10", "15", "20", "30"]
    dates     = ["June 1", "June 15", "July 1", "July 30", "next Friday", "end of month"]
    times_day = ["10 PM", "11 PM", "midnight", "2 AM"]
    contacts  = ["+1312555" + str(1000 + i) for i in range(50)]
    phones    = ["+1" + str(2125550000 + i) for i in range(50)]
    addresses = ["123 Main St, Austin TX 78701", "456 Oak Ave, Chicago IL 60601",
                 "789 Pine Rd, Seattle WA 98101", "101 Maple Dr, Miami FL 33101"]
    countries = ["Mexico", "Canada", "UK", "Germany", "Brazil", "Australia"]
    gbs       = ["5", "10", "20", "50"]
    gb_units  = ["GB", "GB", "GB"]
    years     = ["2", "3", "5", "7", "10"]
    plan_as   = ["Standard", "Premium", "Basic"]
    plan_bs   = ["Premium", "Unlimited Pro", "Standard"]
    days_vals = ["3", "5", "7", "10"]

    all_templates = (billing + technical + activation +
                     account + network + cancellation + upgrades)

    import random
    random.seed(42)

    def substitute(template: str, idx: int) -> str:
        r = random.Random(idx * 7919)
        return (template
            .replace("{acct}",       r.choice(accts))
            .replace("{amount}",     r.choice(amounts))
            .replace("{expected}",   r.choice(expected))
            .replace("{month}",      r.choice(months))
            .replace("{plan}",       r.choice(plans))
            .replace("{old_plan}",   r.choice(old_plans))
            .replace("{new_plan}",   r.choice(new_plans))
            .replace("{location}",   r.choice(locations))
            .replace("{device}",     r.choice(devices))
            .replace("{router_model}", r.choice(routers))
            .replace("{name}",       r.choice(names))
            .replace("{speed}",      r.choice(speeds))
            .replace("{plan_speed}", r.choice(plan_speeds))
            .replace("{minutes}",    r.choice(minutes_vals))
            .replace("{date}",       r.choice(dates))
            .replace("{time}",       r.choice(times_day))
            .replace("{contact}",    r.choice(contacts))
            .replace("{phone}",      r.choice(phones))
            .replace("{address}",    r.choice(addresses))
            .replace("{country}",    r.choice(countries))
            .replace("{gb}",         r.choice(gbs))
            .replace("{years}",      r.choice(years))
            .replace("{plan_a}",     r.choice(plan_as))
            .replace("{plan_b}",     r.choice(plan_bs))
            .replace("{days}",       r.choice(days_vals))
        )

    questions = []
    idx = 0
    while len(questions) < 500:
        for tmpl in all_templates:
            q = substitute(tmpl, idx)
            questions.append(q)
            idx += 1
            if len(questions) == 500:
                break

    return questions


# ──────────────────────────────────────────────────────────────
# Foundry Workflow call using OpenAI Responses API
# (conversations.create + responses.create with agent_reference)
# ──────────────────────────────────────────────────────────────
async def call_agent(
    oai,
    question: str,
    semaphore: asyncio.Semaphore,
    index: int,
) -> dict:
    async with semaphore:
        for attempt in range(1, MAX_RETRIES + 2):
            t0 = time.monotonic()
            conv_id = None
            try:
                loop = asyncio.get_running_loop()

                def _run():
                    conversation = oai.conversations.create()
                    text_chunks = []
                    stream = oai.responses.create(
                        conversation=conversation.id,
                        extra_body={"agent_reference": {"name": AGENT_NAME, "type": "agent_reference"}},
                        input=question,
                        stream=True,
                    )
                    for event in stream:
                        if event.type == "response.output_text.delta":
                            delta = getattr(event, "delta", "")
                            if delta:
                                text_chunks.append(delta)
                    answer = "".join(text_chunks)
                    oai.conversations.delete(conversation_id=conversation.id)
                    return answer

                answer = await loop.run_in_executor(None, _run)
                elapsed = time.monotonic() - t0
                return {
                    "index": index,
                    "question": question,
                    "answer": answer,
                    "status": "completed",
                    "elapsed_s": round(elapsed, 3),
                    "success": True,
                }
            except Exception as exc:
                if attempt <= MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                elapsed = time.monotonic() - t0
                return {
                    "index": index,
                    "question": question,
                    "answer": None,
                    "status": "error",
                    "error": str(exc),
                    "elapsed_s": round(elapsed, 3),
                    "success": False,
                }


async def main():
    print("🔐  Authenticating with AzureCliCredential …")
    credential = AzureCliCredential()
    client     = AIProjectClient(endpoint=ENDPOINT, credential=credential, allow_preview=True)
    oai        = client.get_openai_client()

    # Verify agent exists
    print(f"🔍  Verifying agent '{AGENT_NAME}' exists …")
    agents = list(client.agents.list())
    names  = [a.name for a in agents]
    if AGENT_NAME not in names:
        raise RuntimeError(f"Agent '{AGENT_NAME}' not found. Available: {names}")
    print(f"✅  Agent confirmed: {AGENT_NAME}")

    questions = build_question_bank()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    print(f"\n🚀  Sending {len(questions)} questions (max {MAX_CONCURRENT} concurrent) …\n")
    tasks   = [call_agent(oai, q, semaphore, i) for i, q in enumerate(questions)]
    results = []
    failures = []

    with tqdm(total=len(tasks), unit="conv", ncols=80) as bar:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            if not result["success"]:
                failures.append(result)
            bar.update(1)

    # Sort by original index for deterministic output
    results.sort(key=lambda r: r["index"])

    # ── Persist results ──────────────────────────────────────
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent": AGENT_NAME,
        "endpoint": ENDPOINT,
        "total": len(results),
        "conversations": results,
    }
    RESULTS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    failures_file = RESULTS_FILE.parent / "workflow_failures.json"
    if failures:
        failures_file.write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Summary ──────────────────────────────────────────────
    successful = [r for r in results if r["success"]]
    elapsed_vals = [r["elapsed_s"] for r in successful]
    avg_elapsed  = sum(elapsed_vals) / len(elapsed_vals) if elapsed_vals else 0

    print("\n" + "═" * 55)
    print("  📊  Summary")
    print("═" * 55)
    print(f"  Total conversations : {len(results)}")
    print(f"  Successful          : {len(successful)}  ({len(successful)/len(results)*100:.1f}%)")
    print(f"  Failed              : {len(failures)}")
    print(f"  Avg response time   : {avg_elapsed:.2f}s")
    print(f"  Results saved to    : {RESULTS_FILE}")
    if failures:
        print(f"  Failures saved to   : {failures_file}")
    print("═" * 55)


if __name__ == "__main__":
    asyncio.run(main())
