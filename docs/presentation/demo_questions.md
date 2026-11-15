# Questions for the demo

Checked on 15 November 2026 against the deployed configuration (pipeline 1.0.0, 40 acts, hybrid search). "Rank" is the position of the expected article among the results. These are hand-picked everyday questions, not a benchmark; the measured quality is in `docs/report/final_eval.md`.

| # | Question to paste | Expected article | Rank |
|---|---|---|---|
| 1 | работодатель задерживает зарплату — что делать? | Labor Code, Art. 113 (terms of wage payment) | 1 |
| 2 | можно ли вернуть товар в магазин без чека | Consumer Protection Law, Art. 14 | 1 |
| 3 | меня уволили без предупреждения | Labor Code, Art. 52 (dismissal by the employer) | 1 |
| 4 | сколько длится декрет | Labor Code, Art. 99 (maternity leave) | 1 |
| 5 | как подать на развод если есть дети | Marriage and Family Code, Art. 17–22 | 1 |
| 6 | размер алиментов на одного ребенка | Marriage and Family Code, Art. 139 | 1 |
| 7 | как открыть ИП | Entrepreneurial Code, Art. 33–37 | 1 |
| 8 | какой штраф за езду без прав | Code of Administrative Offences, Art. 612 | 2 |
| 9 | сосед затопил квартиру кто платит | Housing Relations Law, Art. 39 | 2 |
| 10 | сколько могут держать мой телефон в вещдоке | Criminal Procedure Code, Art. 118 and 221 | 3–4 |

## How to use them

- Start with 1 and 2: without the dictionary of everyday words both returned unrelated articles first, so they show what the query expansion does.
- Question 10 is the example of a question the articles do not answer directly: the generated answer says so and then reports what the articles on material evidence do say.
- For Kazakh, switch the source language and ask «Жұмыс уақытының қалыпты ұзақтығы қандай?» (Labor Code, Art. 68).
- Open the cited article after every generated answer. A valid citation shows where the text comes from; it does not prove that the explanation is right.
