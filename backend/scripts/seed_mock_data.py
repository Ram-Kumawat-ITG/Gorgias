# # Seed script — inserts realistic mock tickets, messages, and customers into MongoDB
# # Usage: cd backend && python -m scripts.seed_mock_data
# import asyncio
# import uuid
# from datetime import datetime, timedelta
# from app.database import connect_db, get_db

# # ── Helper ───────────────────────────────────────────────────────────────────
# def uid():
#     return str(uuid.uuid4())

# def ts(days_ago, hours=0, minutes=0):
#     return datetime.utcnow() - timedelta(days=days_ago, hours=hours, minutes=minutes)

# # ── Customers ────────────────────────────────────────────────────────────────
# CUSTOMERS = [
#     {"id": uid(), "email": "priya.sharma@gmail.com", "first_name": "Priya", "last_name": "Sharma", "total_spent": "4520.00", "orders_count": 6, "tags": ["vip"]},
#     {"id": uid(), "email": "james.wilson@outlook.com", "first_name": "James", "last_name": "Wilson", "total_spent": "189.99", "orders_count": 1, "tags": []},
#     {"id": uid(), "email": "sofia.martinez@yahoo.com", "first_name": "Sofia", "last_name": "Martinez", "total_spent": "879.50", "orders_count": 3, "tags": ["returning"]},
#     {"id": uid(), "email": "akash.patel@gmail.com", "first_name": "Akash", "last_name": "Patel", "total_spent": "2150.00", "orders_count": 8, "tags": ["vip", "wholesale"]},
#     {"id": uid(), "email": "emily.chen@icloud.com", "first_name": "Emily", "last_name": "Chen", "total_spent": "320.00", "orders_count": 2, "tags": []},
#     {"id": uid(), "email": "mohammed.ali@hotmail.com", "first_name": "Mohammed", "last_name": "Ali", "total_spent": "67.50", "orders_count": 1, "tags": []},
#     {"id": uid(), "email": "rachel.green@gmail.com", "first_name": "Rachel", "last_name": "Green", "total_spent": "1245.00", "orders_count": 5, "tags": ["returning"]},
#     {"id": uid(), "email": "david.kim@gmail.com", "first_name": "David", "last_name": "Kim", "total_spent": "99.99", "orders_count": 1, "tags": []},
#     {"id": uid(), "email": "ananya.gupta@gmail.com", "first_name": "Ananya", "last_name": "Gupta", "total_spent": "540.00", "orders_count": 4, "tags": ["returning"]},
#     {"id": uid(), "email": "tom.baker@proton.me", "first_name": "Tom", "last_name": "Baker", "total_spent": "0.00", "orders_count": 0, "tags": []},
#     {"id": uid(), "email": "lisa.johnson@gmail.com", "first_name": "Lisa", "last_name": "Johnson", "total_spent": "3200.00", "orders_count": 12, "tags": ["vip"]},
#     {"id": uid(), "email": "raj.verma@yahoo.com", "first_name": "Raj", "last_name": "Verma", "total_spent": "450.00", "orders_count": 2, "tags": []},
#     {"id": uid(), "email": "maria.rossi@gmail.com", "first_name": "Maria", "last_name": "Rossi", "total_spent": "175.00", "orders_count": 1, "tags": []},
#     {"id": uid(), "email": "alex.turner@outlook.com", "first_name": "Alex", "last_name": "Turner", "total_spent": "890.00", "orders_count": 3, "tags": ["returning"]},
#     {"id": uid(), "email": "neha.kapoor@gmail.com", "first_name": "Neha", "last_name": "Kapoor", "total_spent": "1680.00", "orders_count": 7, "tags": ["vip"]},
#     {"id": uid(), "email": "chris.evans@gmail.com", "first_name": "Chris", "last_name": "Evans", "total_spent": "55.00", "orders_count": 1, "tags": []},
#     {"id": uid(), "email": "fatima.sheikh@hotmail.com", "first_name": "Fatima", "last_name": "Sheikh", "total_spent": "720.00", "orders_count": 4, "tags": ["returning"]},
#     {"id": uid(), "email": "mike.brown@gmail.com", "first_name": "Mike", "last_name": "Brown", "total_spent": "2340.00", "orders_count": 9, "tags": ["vip", "wholesale"]},
# ]

# # ── Tickets + Messages ──────────────────────────────────────────────────────
# # Each entry: (ticket_fields, [messages])
# # Messages: (sender_type, body, minutes_after_ticket)

# TICKETS_DATA = [
#     # 1 — Order not received (frustrated)
#     {
#         "subject": "Order #1847 never arrived — it's been 2 weeks!",
#         "customer_email": "priya.sharma@gmail.com",
#         "customer_name": "Priya Sharma",
#         "channel": "email",
#         "status": "open",
#         "priority": "high",
#         "tags": ["shipping", "escalation"],
#         "days_ago": 2,
#         "messages": [
#             ("customer", "Hi, I placed order #1847 on the 10th and it was supposed to arrive within 5 business days. It's now been over 2 weeks and I still haven't received anything. The tracking link you sent hasn't updated since last Monday. This is really frustrating — I ordered this for my daughter's birthday which has already passed. Can someone please look into this urgently?", 0),
#             ("agent", "Hi Priya, I'm really sorry about this delay and I completely understand your frustration, especially since this was for a special occasion. Let me pull up order #1847 right now and check with our shipping partner. I can see the tracking shows it's stuck at the regional sorting facility. I'm going to escalate this directly with the courier and get back to you within the next 2 hours with an update.", 35),
#             ("customer", "Thank you for checking. Please do let me know ASAP. If it's lost I'd like a refund or replacement shipped express.", 42),
#             ("agent", "Absolutely, Priya. I've filed an investigation with the courier. If we don't have movement within 24 hours, I'll process either a full refund or an express replacement — whichever you prefer. I'll update you tomorrow morning at the latest.", 50),
#         ],
#     },
#     # 2 — Refund request (polite)
#     {
#         "subject": "Refund request for order #2103",
#         "customer_email": "james.wilson@outlook.com",
#         "customer_name": "James Wilson",
#         "channel": "email",
#         "status": "pending",
#         "priority": "normal",
#         "tags": ["refund"],
#         "days_ago": 5,
#         "messages": [
#             ("customer", "Hello, I received my order #2103 yesterday but unfortunately the color of the jacket is quite different from what was shown on the website. It looked navy blue online but in person it's more of a dark grey. I'd like to return it for a refund if possible. The item is unworn with tags still attached.", 0),
#             ("agent", "Hi James, thank you for reaching out! I'm sorry the color didn't match your expectations — that's definitely not the experience we want. I'd be happy to process a refund for you. I've just emailed you a prepaid return label. Once you drop it off at any UPS location and we receive it back (usually 3-5 business days), we'll issue the refund to your original payment method. Is there anything else I can help with?", 120),
#             ("customer", "That's great, thank you! I got the return label. I'll drop it off tomorrow. Appreciate the quick response.", 140),
#             ("agent", "You're welcome, James! Once it's shipped, just let us know the drop-off confirmation and we'll keep an eye on it. Have a great day!", 145),
#         ],
#     },
#     # 3 — Wrong product (upset)
#     {
#         "subject": "Received completely wrong item",
#         "customer_email": "sofia.martinez@yahoo.com",
#         "customer_name": "Sofia Martinez",
#         "channel": "chat",
#         "status": "open",
#         "priority": "high",
#         "tags": ["wrong-item", "urgent"],
#         "days_ago": 1,
#         "messages": [
#             ("customer", "I ordered a women's medium red dress (order #3056) and instead I got a men's XL blue hoodie?? This isn't even close to what I ordered. I need the correct item shipped out TODAY because I have an event this Saturday.", 0),
#             ("agent", "Oh no, Sofia — I'm so sorry about that mix-up! That's clearly a warehouse error on our end. Let me get this sorted immediately. I'm processing an express shipment of the correct item (Women's Medium Red Dress) right now with overnight delivery so you'll have it by Friday. You don't need to return the hoodie — consider it on us for the inconvenience.", 8),
#             ("customer", "Ok that sounds good. Are you 100% sure it'll arrive by Friday? I really can't afford for this to go wrong again.", 12),
#             ("agent", "I've confirmed with our fulfillment team — it's being packed now and will ship within the hour via overnight express. I'll send you the tracking number as soon as it's dispatched. You'll have it by tomorrow evening at the latest. I'm also adding a 20% discount code to your account for the trouble.", 18),
#             ("customer", "Alright thank you. I'll be watching for that tracking number.", 22),
#         ],
#     },
#     # 4 — Login/account issue (confused)
#     {
#         "subject": "Can't log into my account anymore",
#         "customer_email": "akash.patel@gmail.com",
#         "customer_name": "Akash Patel",
#         "channel": "chat",
#         "status": "resolved",
#         "priority": "normal",
#         "tags": ["account", "login"],
#         "days_ago": 7,
#         "messages": [
#             ("customer", "hey i cant log in to my account. it keeps saying invalid password but im using the same password i always use. tried resetting it 3 times and the reset email never comes through. my email is akash.patel@gmail.com", 0),
#             ("agent", "Hi Akash! Sorry you're having trouble getting in. Let me check your account. I can see the reset emails were sent but they might be landing in your spam/junk folder — could you check there? Also, make sure you're checking gmail specifically since that's the email on your account.", 5),
#             ("customer", "oh wait.. let me check spam. hold on", 7),
#             ("customer", "found it! it was in spam. im in now. sorry about that lol", 10),
#             ("agent", "No worries at all, glad that worked! I'd recommend marking emails from us as 'not spam' so they come through normally going forward. Let me know if you need anything else!", 12),
#             ("customer", "will do, thanks!", 13),
#         ],
#     },
#     # 5 — Payment failed
#     {
#         "subject": "Payment keeps getting declined",
#         "customer_email": "emily.chen@icloud.com",
#         "customer_name": "Emily Chen",
#         "channel": "email",
#         "status": "open",
#         "priority": "normal",
#         "tags": ["payment"],
#         "days_ago": 0,
#         "messages": [
#             ("customer", "Hi there, I've been trying to complete my purchase for the past hour but my card keeps getting declined. I've tried two different cards and both fail at checkout. There's definitely enough balance on both cards. I've made purchases on other sites today with no issues. Is there a problem with your payment system?", 0),
#             ("agent", "Hi Emily, thanks for letting us know. I'm sorry about the checkout trouble. I've checked our payment processor status and everything looks operational on our end. A few things to try:\n\n1. Clear your browser cache and cookies, then try again\n2. Try using a different browser or incognito mode\n3. Make sure your billing address matches exactly what's on file with your bank\n\nIf none of those work, could you share the last 4 digits of the card and I can check for any specific error codes on our end?", 45),
#         ],
#     },
#     # 6 — Subscription cancellation
#     {
#         "subject": "Please cancel my subscription",
#         "customer_email": "mohammed.ali@hotmail.com",
#         "customer_name": "Mohammed Ali",
#         "channel": "email",
#         "status": "resolved",
#         "priority": "low",
#         "tags": ["subscription", "cancellation"],
#         "days_ago": 10,
#         "messages": [
#             ("customer", "Hi, I'd like to cancel my monthly subscription. I signed up for the trial and forgot to cancel before it renewed. Is it possible to also get a refund for this month since I haven't used the service at all?", 0),
#             ("agent", "Hi Mohammed, I've gone ahead and cancelled your subscription effective immediately — you won't be charged again. Since you haven't used the service this billing cycle, I've also processed a full refund of $12.99 which should appear on your statement within 3-5 business days. Is there anything else I can help with?", 90),
#             ("customer", "That was easier than I expected. Thank you very much!", 100),
#             ("agent", "Happy to help! If you ever want to come back, your account and settings will be saved. Have a great day, Mohammed!", 105),
#         ],
#     },
#     # 7 — Product inquiry
#     {
#         "subject": "Question about wireless earbuds compatibility",
#         "customer_email": "rachel.green@gmail.com",
#         "customer_name": "Rachel Green",
#         "channel": "chat",
#         "status": "resolved",
#         "priority": "low",
#         "tags": ["pre-sale", "product-info"],
#         "days_ago": 3,
#         "messages": [
#             ("customer", "Hi! Quick question — do the ProSound X3 earbuds work with Samsung Galaxy phones? The product page only mentions iPhone compatibility", 0),
#             ("agent", "Hi Rachel! Great question — yes, the ProSound X3 earbuds are fully compatible with all Samsung Galaxy phones! They use standard Bluetooth 5.3, so they'll work with any Bluetooth-enabled device. The product page mentions iPhone because of the dedicated iOS app for EQ settings, but the Android app works just as well. Would you like me to share a link to the Android app?", 3),
#             ("customer", "Oh perfect! No that's fine, I can find the app. Going to order them now. Thanks!", 5),
#             ("agent", "Awesome, you'll love them! Let us know if you have any questions once they arrive. Enjoy! 🎧", 6),
#         ],
#     },
#     # 8 — Damaged product (very frustrated)
#     {
#         "subject": "Package arrived completely destroyed",
#         "customer_email": "david.kim@gmail.com",
#         "customer_name": "David Kim",
#         "channel": "email",
#         "status": "open",
#         "priority": "urgent",
#         "tags": ["damaged", "urgent", "escalation"],
#         "days_ago": 0,
#         "messages": [
#             ("customer", "I just received my order #4521 and the box looks like it was run over by a truck. The ceramic vase set I ordered is completely shattered — every single piece broken. I paid $99 for this and it's a pile of ceramic dust. This is the second time I've had shipping damage from your store. Honestly considering never ordering again. I want a full refund AND I think you need to switch your shipping carrier because this is unacceptable.", 0),
#         ],
#     },
#     # 9 — Discount code not working
#     {
#         "subject": "Promo code SUMMER25 not working at checkout",
#         "customer_email": "ananya.gupta@gmail.com",
#         "customer_name": "Ananya Gupta",
#         "channel": "whatsapp",
#         "status": "pending",
#         "priority": "low",
#         "tags": ["discount", "checkout"],
#         "days_ago": 1,
#         "messages": [
#             ("customer", "hi i got an email saying i can use code SUMMER25 for 25% off but when i put it in at checkout it says code is invalid. Can you help?", 0),
#             ("agent", "Hey Ananya! Let me check on that code for you. I see the issue — SUMMER25 is valid for orders above $50 and it looks like your cart total is $47.50 before the discount. If you add any item to bring it above $50, the code should work! Alternatively, I can apply a manual $10 discount to your current order if you'd like to proceed now.", 15),
#             ("customer", "oh i didnt see the minimum. ill just add something small. thanks for explaining", 20),
#         ],
#     },
#     # 10 — Size exchange
#     {
#         "subject": "Need to exchange for a different size",
#         "customer_email": "tom.baker@proton.me",
#         "customer_name": "Tom Baker",
#         "channel": "email",
#         "status": "pending",
#         "priority": "low",
#         "tags": ["exchange", "sizing"],
#         "days_ago": 4,
#         "messages": [
#             ("customer", "Hi, I bought the Classic Fit Denim Jacket in Large (order #5678) but it's a bit too snug around the shoulders. Would it be possible to exchange it for an XL? I've only tried it on, tags are still on.", 0),
#             ("agent", "Hi Tom! Absolutely, we can arrange that exchange for you. I've checked and the XL is in stock. Here's what we'll do:\n\n1. I'll email you a prepaid return label for the Large\n2. I'll reserve the XL and ship it out today so you don't have to wait\n3. Just send back the Large within 14 days\n\nDoes that work for you?", 180),
#             ("customer", "That's really helpful actually, didn't expect you'd send the new one before getting the return. Yes please go ahead!", 200),
#             ("agent", "Done! The XL is shipping today. You'll get a tracking email within the hour and the return label is in a separate email. No rush on sending the Large back — you've got 14 days. Enjoy the jacket, Tom!", 210),
#         ],
#     },
#     # 11 — Shopify order inquiry
#     {
#         "subject": "Shopify Order #1092 — tracking shows delivered but nothing here",
#         "customer_email": "lisa.johnson@gmail.com",
#         "customer_name": "Lisa Johnson",
#         "channel": "shopify",
#         "status": "open",
#         "priority": "high",
#         "tags": ["shopify", "shipping", "lost-package"],
#         "days_ago": 1,
#         "shopify_order_id": "mock-shopify-1092",
#         "shopify_order_number": "1092",
#         "shopify_financial_status": "paid",
#         "shopify_fulfillment_status": "fulfilled",
#         "shopify_total_price": "245.00",
#         "shopify_currency": "USD",
#         "shopify_line_items": [
#             {"title": "Merino Wool Sweater", "quantity": 1, "price": "129.00"},
#             {"title": "Silk Scarf", "quantity": 2, "price": "58.00"},
#         ],
#         "messages": [
#             ("customer", "The tracking for my order says 'delivered' as of yesterday but I've checked my front door, side door, mailroom, and even asked my neighbors. Nobody has it. I was home all day and no delivery person came. Can you help figure out where my package actually is?", 0),
#             ("agent", "Hi Lisa, I'm sorry about this — I know how frustrating that is. I can see the tracking does show delivered, but sometimes the carrier marks it early. I'm going to:\n\n1. File a missing package claim with the carrier right now\n2. Check if the driver left any delivery notes or photo proof\n\nCan you confirm your shipping address is still 742 Evergreen Terrace? I want to make sure it wasn't misrouted.", 25),
#             ("customer", "Yes that's correct. I've been at this address for 3 years, never had this issue before.", 30),
#         ],
#     },
#     # 12 — Technical issue with product
#     {
#         "subject": "Smart watch won't charge after a week",
#         "customer_email": "raj.verma@yahoo.com",
#         "customer_name": "Raj Verma",
#         "channel": "chat",
#         "status": "open",
#         "priority": "normal",
#         "tags": ["technical", "warranty"],
#         "days_ago": 2,
#         "messages": [
#             ("customer", "bought the TechFit Pro watch last week and it was working fine until yesterday. now it wont charge at all. tried different cables and power adapters. the charging indicator doesnt even light up. is this covered under warranty?", 0),
#             ("agent", "Hi Raj, sorry to hear about the charging issue! Yes, this is fully covered under our 1-year warranty. Before we process a replacement, let me walk you through a quick reset that sometimes fixes this:\n\n1. Hold the side button + crown for 15 seconds until you see the logo\n2. Place it on the charger for at least 30 minutes uninterrupted\n3. Try a different outlet (not a power strip)\n\nDid any of those work?", 6),
#             ("customer", "tried all three, nothing. the screen is completely dead now too.", 15),
#             ("agent", "Alright, sounds like a hardware issue. I'm going to process a warranty replacement for you right away. I'll send you a shipping label for the defective unit and dispatch a brand new one. You should receive the replacement in 2-3 business days. I'll email you all the details in a moment.", 18),
#         ],
#     },
#     # 13 — Bulk order inquiry
#     {
#         "subject": "Corporate order — need 50 units with custom branding",
#         "customer_email": "mike.brown@gmail.com",
#         "customer_name": "Mike Brown",
#         "channel": "email",
#         "status": "pending",
#         "priority": "high",
#         "tags": ["wholesale", "corporate", "custom"],
#         "days_ago": 3,
#         "messages": [
#             ("customer", "Hello, I'm the procurement manager at TechStart Inc. We're looking to order 50 units of the Executive Leather Portfolio for our company retreat next month. Two questions:\n\n1. Do you offer bulk pricing for orders this size?\n2. Can you do custom embossing with our company logo?\n\nWe'd need delivery by April 15th. Please let me know if this is feasible.", 0),
#             ("agent", "Hi Mike, thanks for reaching out! We'd love to work with TechStart on this. To answer your questions:\n\n1. Yes! For 50+ units we offer 30% off the retail price, bringing each portfolio to $48.30 (down from $69.00)\n2. Custom embossing is available — we just need a vector file (SVG or AI) of your logo. There's a one-time setup fee of $75.\n\nTotal estimate: $2,415 + $75 setup = $2,490\nTimeline: 10-12 business days from logo approval, so April 15th is definitely achievable if we get started this week.\n\nShall I prepare a formal quote?", 240),
#             ("customer", "That pricing works for us. Yes please send a formal quote — I'll need it for our finance approval. I'll have our designer send the logo file today.", 280),
#         ],
#     },
#     # 14 — Complaint about customer service (angry)
#     {
#         "subject": "THIRD time contacting about the same issue",
#         "customer_email": "maria.rossi@gmail.com",
#         "customer_name": "Maria Rossi",
#         "channel": "email",
#         "status": "open",
#         "priority": "urgent",
#         "tags": ["escalation", "repeat-contact", "urgent"],
#         "days_ago": 0,
#         "messages": [
#             ("customer", "This is my THIRD email about order #7890. First person said the refund was processed 2 weeks ago. Second person said they had no record of any refund. Now two weeks later I still don't have my $175 back and nobody seems to know what's going on. This is completely unacceptable. I want a manager to handle this because clearly your regular support isn't getting it done. If this isn't resolved by end of day I'm filing a chargeback and leaving reviews everywhere.", 0),
#         ],
#     },
#     # 15 — WhatsApp casual inquiry
#     {
#         "subject": "do you ship to canada?",
#         "customer_email": "alex.turner@outlook.com",
#         "customer_name": "Alex Turner",
#         "channel": "whatsapp",
#         "status": "resolved",
#         "priority": "low",
#         "tags": ["shipping", "international"],
#         "days_ago": 6,
#         "messages": [
#             ("customer", "hey do u guys ship to canada? im in toronto", 0),
#             ("agent", "Hey Alex! Yes we do ship to Canada! Standard shipping to Toronto is usually 7-10 business days and costs $12.95 flat rate. We also have express (3-5 days) for $24.95. Just heads up — orders over $100 CAD might have a small customs/duty charge on delivery.", 4),
#             ("customer", "nice ok. and returns work the same?", 6),
#             ("agent", "Returns are free within Canada too! We provide a prepaid label. Same 30-day return window as domestic orders.", 8),
#             ("customer", "perfect thx 👍", 9),
#         ],
#     },
#     # 16 — Feature request
#     {
#         "subject": "Suggestion: add Apple Pay at checkout",
#         "customer_email": "neha.kapoor@gmail.com",
#         "customer_name": "Neha Kapoor",
#         "channel": "email",
#         "status": "closed",
#         "priority": "low",
#         "tags": ["feedback", "feature-request"],
#         "days_ago": 14,
#         "messages": [
#             ("customer", "Hi! Love your products — been a customer for over a year now. Just a suggestion: it would be really convenient if you added Apple Pay as a checkout option. I use it everywhere else and having to type in card details each time is a bit of a hassle. Not a complaint, just feedback!", 0),
#             ("agent", "Hi Neha, thank you so much for the suggestion and for being a loyal customer! You'll be happy to know that Apple Pay support is actually on our development roadmap — we're aiming to launch it in the next 2-3 months. I've added your feedback to our tracking list so the product team knows there's demand. In the meantime, you can save your card details in your account settings to speed up checkout. Thanks again!", 360),
#             ("customer", "Oh that's great to hear! Looking forward to it. Thanks!", 380),
#         ],
#     },
#     # 17 — Shipping address change (urgent)
#     {
#         "subject": "URGENT — need to change shipping address on order placed 10 min ago",
#         "customer_email": "chris.evans@gmail.com",
#         "customer_name": "Chris Evans",
#         "channel": "chat",
#         "status": "resolved",
#         "priority": "high",
#         "tags": ["shipping", "address-change"],
#         "days_ago": 2,
#         "messages": [
#             ("customer", "I JUST placed order #8234 like 10 minutes ago and I realized it's shipping to my old address!! Can you please change it before it ships? New address is 156 Oak Street, Apt 4B, Brooklyn, NY 11201", 0),
#             ("agent", "Hi Chris, let me check on this right away! Good news — the order hasn't been picked yet so I can still update it. I've changed the shipping address to:\n\n156 Oak Street, Apt 4B\nBrooklyn, NY 11201\n\nYou'll receive an updated confirmation email shortly. Crisis averted! 😄", 3),
#             ("customer", "omg thank you so much!! that was fast. you saved me 🙏", 4),
#             ("agent", "Happy to help, Chris! Enjoy your order when it arrives at the right place! 😊", 5),
#         ],
#     },
#     # 18 — Multiple items inquiry
#     {
#         "subject": "Which moisturizer is best for sensitive skin?",
#         "customer_email": "fatima.sheikh@hotmail.com",
#         "customer_name": "Fatima Sheikh",
#         "channel": "chat",
#         "status": "resolved",
#         "priority": "low",
#         "tags": ["pre-sale", "product-info", "skincare"],
#         "days_ago": 5,
#         "messages": [
#             ("customer", "Hi, I'm looking at your moisturizers but there are so many options and I have really sensitive skin that reacts to a lot of products. I've tried CeraVe and it broke me out. Can you recommend something that's fragrance-free and gentle?", 0),
#             ("agent", "Hi Fatima! Great question. For sensitive skin that reacts easily, I'd recommend our HydraCalm Daily Moisturizer. Here's why:\n\n- Completely fragrance-free and hypoallergenic\n- Contains ceramides and oat extract (soothing, not irritating)\n- No essential oils, no parabens\n- It's actually formulated differently from CeraVe — uses a lighter base that's less likely to clog pores\n\nWe also have a travel-size for $12 if you want to patch-test before committing to the full size ($38). Would you like me to add either to your cart?", 4),
#             ("customer", "the travel size is smart, I'll start with that. can you send me the link?", 8),
#             ("agent", "Here you go! I've also added a 10% first-purchase code GENTLE10 since I see you haven't ordered skincare from us before. It works on the travel size too!", 10),
#             ("customer", "aww that's sweet thank you! just ordered it", 15),
#             ("agent", "Wonderful! If you have any reactions or questions once you try it, don't hesitate to reach out. Hope your skin loves it! ✨", 16),
#         ],
#     },
#     # 19 — Shopify order — refund for partial items
#     {
#         "subject": "Shopify Order #1205 — one item was missing from package",
#         "customer_email": "priya.sharma@gmail.com",
#         "customer_name": "Priya Sharma",
#         "channel": "shopify",
#         "status": "pending",
#         "priority": "normal",
#         "tags": ["shopify", "missing-item", "partial-refund"],
#         "days_ago": 3,
#         "shopify_order_id": "mock-shopify-1205",
#         "shopify_order_number": "1205",
#         "shopify_financial_status": "paid",
#         "shopify_fulfillment_status": "fulfilled",
#         "shopify_total_price": "189.00",
#         "shopify_currency": "USD",
#         "shopify_line_items": [
#             {"title": "Organic Cotton T-Shirt (White)", "quantity": 2, "price": "35.00"},
#             {"title": "Linen Pants (Navy)", "quantity": 1, "price": "89.00"},
#             {"title": "Canvas Tote Bag", "quantity": 1, "price": "30.00"},
#         ],
#         "messages": [
#             ("customer", "I received my order today but the Canvas Tote Bag is missing from the package. I got the t-shirts and the pants but no tote bag. The packing slip shows it should have been included.", 0),
#             ("agent", "Hi Priya, I apologize for the missing item! I can confirm from our warehouse records that the Canvas Tote Bag should have been in the same shipment. I have two options for you:\n\n1. We ship the missing tote bag right away (2-3 day delivery)\n2. We refund you $30 for the missing item\n\nWhich would you prefer?", 60),
#             ("customer", "Please just ship it — I actually really wanted the bag. Can it come any faster?", 70),
#         ],
#     },
#     # 20 — General positive feedback
#     {
#         "subject": "Just wanted to say thanks!",
#         "customer_email": "lisa.johnson@gmail.com",
#         "customer_name": "Lisa Johnson",
#         "channel": "email",
#         "status": "closed",
#         "priority": "low",
#         "tags": ["feedback", "positive"],
#         "days_ago": 8,
#         "messages": [
#             ("customer", "Hi team, I don't usually write in just to say nice things but I wanted to let you know that Sarah who helped me last week with my return was absolutely amazing. She went above and beyond to make sure everything was sorted quickly and even followed up afterwards to check I received my exchange. That kind of service is rare these days. Please pass on my thanks to her and her manager!", 0),
#             ("agent", "Hi Lisa, wow — thank you so much for taking the time to share this! Messages like yours truly make our day. I've forwarded your feedback directly to Sarah and her team lead, and it'll be noted in her performance review. We're lucky to have customers like you too! Is there anything else we can help with?", 180),
#             ("customer", "Nope, just wanted to spread some positivity! Have a great week 😊", 200),
#         ],
#     },
# ]


# async def main():
#     await connect_db()
#     db = get_db()

#     # ── Clear existing mock data ─────────────────────────────────────────────
#     print("Clearing existing data...")
#     await db.tickets.delete_many({})
#     await db.messages.delete_many({})
#     await db.customers.delete_many({})
#     await db.activity_logs.delete_many({})
#     print("Cleared.")

#     # ── Insert customers ─────────────────────────────────────────────────────
#     print("Inserting customers...")
#     for c in CUSTOMERS:
#         doc = {
#             **c,
#             "created_at": ts(30),
#             "updated_at": ts(1),
#         }
#         await db.customers.update_one(
#             {"email": c["email"]},
#             {"$set": doc},
#             upsert=True,
#         )
#     print(f"  {len(CUSTOMERS)} customers inserted.")

#     # ── Insert tickets + messages ────────────────────────────────────────────
#     print("Inserting tickets and messages...")
#     ticket_count = 0
#     message_count = 0

#     for td in TICKETS_DATA:
#         ticket_id = uid()
#         created = ts(td["days_ago"])

#         ticket_doc = {
#             "id": ticket_id,
#             "subject": td["subject"],
#             "customer_email": td["customer_email"],
#             "customer_name": td.get("customer_name"),
#             "channel": td["channel"],
#             "status": td["status"],
#             "priority": td["priority"],
#             "tags": td.get("tags", []),
#             "sla_status": "ok",
#             "created_at": created,
#             "updated_at": created,
#         }

#         # Add Shopify-specific fields if present
#         for key in ("shopify_order_id", "shopify_order_number", "shopify_financial_status",
#                      "shopify_fulfillment_status", "shopify_total_price", "shopify_currency",
#                      "shopify_line_items"):
#             if key in td:
#                 ticket_doc[key] = td[key]

#         # Set resolved_at for resolved/closed tickets
#         if td["status"] in ("resolved", "closed"):
#             ticket_doc["resolved_at"] = created + timedelta(hours=2)

#         # Set first_response_at if there's an agent message
#         agent_msgs = [m for m in td["messages"] if m[0] == "agent"]
#         if agent_msgs:
#             ticket_doc["first_response_at"] = created + timedelta(minutes=agent_msgs[0][2])

#         await db.tickets.insert_one(ticket_doc)
#         ticket_count += 1

#         # Insert messages
#         for sender_type, body, minutes_offset in td["messages"]:
#             msg_doc = {
#                 "id": uid(),
#                 "ticket_id": ticket_id,
#                 "body": body,
#                 "sender_type": sender_type,
#                 "is_internal_note": False,
#                 "ai_generated": False,
#                 "attachments": [],
#                 "created_at": created + timedelta(minutes=minutes_offset),
#             }
#             await db.messages.insert_one(msg_doc)
#             message_count += 1

#         # Insert activity log
#         await db.activity_logs.insert_one({
#             "id": uid(),
#             "entity_type": "ticket",
#             "entity_id": ticket_id,
#             "customer_email": td["customer_email"],
#             "event": "ticket.created",
#             "actor_type": "system",
#             "description": f"Ticket created: {td['subject']}",
#             "created_at": created,
#         })

#     print(f"  {ticket_count} tickets inserted.")
#     print(f"  {message_count} messages inserted.")
#     print("\nDone! Mock data is ready.")


# asyncio.run(main())
