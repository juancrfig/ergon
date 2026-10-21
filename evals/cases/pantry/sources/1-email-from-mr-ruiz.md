From: Tomás Ruiz <tomas@ruizbakery.example>
Date: 2026-10-20
Subject: Two things for the stock program

Hello,

We use the stock program in the `pantry` repo every day at the bakery. It works well. I need two more things.

1. An order list. `python3 pantry.py reorder` tells me what to order today. One line per item that needs an order,
   in the same order as the `stock` list, like this:

       flour: 3 x 25 kg from Molinos Andinos

   That is the number of packs, the size of one pack and the supplier. Order the way we always order: an item needs
   an order when it is under its minimum, and then we buy enough to get back to our usual level. Our suppliers only
   sell whole packs, and some of them have a minimum order. Write quantities the way the program already writes them.
   When nothing needs an order, print `Nothing to order.`

2. Planning what we bake. `python3 pantry.py plan croissant 2` means we will bake two batches of croissants. It
   prints `Planned croissant x 2.` and then, for each ingredient we do not have enough of, a line like
   `Short of butter: 1.5 kg`, in the same order as the `stock` list. The number of batches must be a whole number
   above 0; otherwise print `Batches must be a whole number above 0.` to the error output and exit with code 1.

   Once a bake is planned, the order list must count it too: what we will bake uses up stock, so we may need to
   order more.

Everything else should keep working as it does now.

Thanks,
Tomás Ruiz
