# Ghi chú cho người trình bày

Trích từ phần ghi chú (`<aside>`) của từng slide trong `deck/slides/`. Thứ tự theo `deck/deck.json`.

## 1. Autoformalization Pipeline

Giới thiệu nhóm và đề tài. Nhóm 5 xây một pipeline phân tán: LLM dịch đề toán ngôn ngữ tự nhiên thành phát biểu Lean 4, Lean kiểm chứng hàng loạt, rồi đo khả năng mở rộng tới 10.000 task. Dòng mã trên slide là một phát biểu thật trong corpus của nhóm. Bộ slide đi theo đúng các bước của bản thiết kế tuần 2 và trả lời hai câu hỏi của đề bài; số liệu chi tiết và log thô nằm trong báo cáo và bộ code.

## 2. Dịch đề toán sang Lean 4, rồi để Lean kiểm chứng

Ví dụ thật lấy từ corpus. Đầu vào là một đề GSM8K kèm đáp án. LLM sinh một phát biểu Lean có biến, giả thiết và kết luận khẳng định đáp án; phần chứng minh để sorry vì nhóm kiểm chứng phát biểu, chưa chứng minh. Worker Lean giữ sẵn một REPL đã nạp Mathlib nên ứng viên này compile trong 12,7 ms, và bộ kiểm tra ngữ nghĩa còn tự suy ra được kyle = 14 từ giả thiết. Nhưng compile chỉ nói phát biểu đúng kiểu, không nói nó đúng đề; với hàng nghìn bài thì không thể đọc tay từng bài. Đó là câu hỏi thứ hai của đề bài.

## 3. Batching và số candidate ảnh hưởng thế nào tới throughput, chi phí và compile rate?

Đây là hai câu hỏi nghiên cứu mà hướng dẫn bài tập lớn đặt cho Nhóm 5, và cũng là khung cho phần còn lại. Câu 1 hỏi về batching và số candidate: nhóm đo ở cả hai tầng, gom bao nhiêu bài vào một request tới mô hình, và lô bao nhiêu task cho mỗi lần Lean worker lấy việc; cùng với 1 so với 4 candidate mỗi bài. Câu 2 hỏi cách phát hiện phát biểu Lean chấp nhận nhưng sai nghĩa: ba lớp kiểm tra, mỗi lớp đều được đo độ tin cậy. Câu hỏi trên slide môn học về vai trò Big Data được trả lời bằng các thí nghiệm mà kết luận thay đổi khi dữ liệu tăng từ 100 lên 10.000 task.

## 4. 22.150 đề thật từ bốn nguồn công khai

Bốn nguồn công khai, đều tải được từ GitHub. ProofNet và miniF2F có phát biểu Lean do người viết, dùng làm tham chiếu ngữ nghĩa; MATH và GSM8K có đáp án. Mỗi bài là một DataUnit. Khoá phân vùng dùng SHA-256 vì hash() của Python bị salt khác nhau giữa các tiến trình, nên hai máy sẽ tính ra hai partition khác nhau. Lưu lâu dài bằng Parquet phân vùng theo source và domain, truy vấn thẳng bằng DuckDB hoặc Spark. Ba tầng lồng nhau giữ cùng tỷ lệ nguồn. Theo yêu cầu tiết kiệm, nhóm chỉ sinh mã cho 1.000 bài; tầng 10K là trace replay: Lean kiểm chứng lại đủ 10.000 task nhưng không gọi lại model. Hướng dẫn gợi ý NuminaMath-CoT, nhưng HuggingFace không truy cập được từ môi trường thí nghiệm; MATH và GSM8K là hai nguồn con của nó, cùng vai trò: nhiều bài có đáp án, không có nhãn hình thức. Theo yêu cầu dữ liệu, Git chỉ giữ mẫu 100 bài, các split, manifest có SHA-256 và script tải lại.

## 5. Bốn tầng nối với nhau bằng hàng đợi phân vùng

Pipeline đi đúng luồng của thiết kế tuần 2: hàng đợi đề, batch inference, pool Lean, rồi tổng hợp. Hai hàng đợi tách việc sinh mã khỏi việc kiểm chứng, nên mỗi tầng tăng số worker độc lập và một worker hỏng không làm sập cả luồng. Nhóm không dùng MapReduce thuần vì worker Lean phải giữ trạng thái: chạy lạnh mất 16,7–24 giây mỗi ứng viên chỉ để nạp lại Mathlib, nên mỗi worker nạp một lần rồi kiểm chứng hàng nghìn ứng viên. Hai lớp giới hạn: maxHeartbeats dừng phần lớn ca chậm một cách có kiểm soát, hard timeout là lưới an toàn. Mọi task có khoá TaskHash và mọi lần ghi là UPSERT, nên chạy lại bao nhiêu lần kết quả cuối vẫn như nhau. Broker đổi bằng cấu hình: SQLite cho một máy, Redis Streams cho nhiều máy.

## 6. Một baseline, tám yếu tố, hai metric chính

Baseline đúng theo mục 7 của hướng dẫn: zero-shot, mỗi request một bài, một candidate, Lean kiểm tra bằng một worker, không repair. Trong môi trường của nhóm, gửi riêng từng bài tốn khoảng 87 nghìn token mỗi bài, nên baseline sinh mã chạy trên 20 bài phân tầng; ở ba mức 100, 1.000 và 10.000 bài, ứng viên zero-shot cùng prompt được kiểm chứng bằng đúng cấu hình một worker, lô 1. Tám yếu tố được thay đổi, đủ sáu yếu tố hướng dẫn liệt kê cộng hai ablation. Nhóm chọn hai metric chính: độ chính xác ngữ nghĩa trên tập audit cho chất lượng và throughput ổn định cho hệ thống; các chỉ số còn lại để giải thích trade-off. Mỗi lần chạy ghi một run record theo Phụ lục B của hướng dẫn, và lưới tham số nằm trong configs/experiments.json.

## 7. Compile gần như bão hòa: 98,9 % trên 1.000 bài

Với Claude Haiku 5.5, compile gần như bão hòa: 98,9 % ngay ở mẫu đầu tiên, ProofNet thấp nhất vì toàn định lý đại học. Baseline bắt buộc, mỗi request một bài, chạy trên 20 bài phân tầng và được so với ứng viên batch job của chính 20 bài đó, cùng cấu hình kiểm chứng một worker: chất lượng như nhau, cả hai đều 20 trên 20 compile và 2 trên 20 bị gắn cờ, nhưng gửi riêng từng bài tốn hơn 87 nghìn token mỗi bài so với khoảng 2 nghìn khi gom. Phân loại lỗi theo nguyên nhân gốc cho thấy 7 trong 17 lỗi ban đầu là lỗi của chính sanitizer của nhóm; vì output thô của mô hình được lưu nguyên, sửa sanitizer chỉ cần chạy lại bước hậu xử lý, không gọi lại mô hình lần nào. Vì compile đã bão hòa, chất lượng thật phải đo bằng ngữ nghĩa, là câu hỏi thứ hai.

## 8. Gom 20–26 bài mỗi request: rẻ hơn 42 lần, ít hỏng

Câu hỏi 1 ở tầng inference. Gửi riêng từng bài tốn hơn 87 nghìn token mỗi bài, vì mỗi request mang một phần ngữ cảnh cố định, khoảng 80 nghìn token trong môi trường của nhóm; qua API trực tiếp phần cố định nhỏ hơn nhiều nhưng xu hướng giống nhau. Gom 20 đến 26 bài vào một request, chi phí đó được chia đều: còn khoảng 2 nghìn token mỗi bài, rẻ hơn 42 lần, và chỉ 7,7 % request bị hỏng. Gom quá tay, 100 đến 142 bài, thì rẻ thêm rất ít nhưng 58 % request hỏng hoặc thiếu bài, vì chạm giới hạn token đầu ra của mỗi lần trả lời. Nên lô ở tầng này phải chia theo ngân sách token, không theo số bài. Về số candidate: 4 mẫu few-shot đưa Pass@4 lên 100 % nhưng tốn gấp 4 lần token và không làm phát biểu đúng nghĩa hơn; few-shot giảm tỷ lệ bị gắn cờ từ 17,2 xuống 13 %. Không gửi lại phần thiếu thì chỉ có 56 % ứng viên; gửi lại theo TaskHash trong các request nhỏ hơn thì đủ 100 %.

## 9. Lô 1, 8 hay 32 task: throughput như nhau ở 2 worker

Câu hỏi 1 ở tầng kiểm chứng: lô là số task một worker lấy mỗi lần lease. Nhóm chạy 36 lần: lô 1, lô 1 có index, lô 8 và lô 32, ở 100, 1.000 và 10.000 task, mỗi ô 3 lần, 2 worker, timeout 30 giây. Kết quả: batch size gần như không đổi throughput. Ở 100 và 1.000 bài là khoảng 1,6 và 10,8–11,2 bài mỗi giây với mọi lô, vì khởi động REPL khoảng 57 giây chiếm phần lớn thời gian. Ở 10.000 task là 16,0–18,8 bài mỗi giây; mỗi lần chạy gặp 2–6 timeout và mỗi timeout kéo theo khởi động lại REPL, nên số timeout chứ không phải batch size quyết định lần chạy nhanh hay chậm. Chi phí lease chỉ vài mili giây, nhỏ so với khoảng 30 mili giây mỗi lần kiểm. Lô 32 ở 100 bài hơi kém vì chỉ có 4 lô, cuối lần chạy một worker ngồi không. Index hàng đợi chỉ cần khi backlog lên 100 nghìn task. Lưu ý: các lần chạy này trên máy đợt 26/10, chậm hơn máy đợt 16/10, nên chỉ so trong cùng đợt.

## 10. Ở 10.000 task, kết luận khác hẳn ở 100 task

Vai trò Big Data được chứng minh bằng những thí nghiệm mà kết luận thay đổi theo quy mô. Ở 100 bài, một tiến trình là đủ và nhanh nhất. Ở 10.000 task thì khác. Chi phí nạp Mathlib phải trả một lần cho mỗi worker: REPL nóng nhanh hơn chạy lạnh 442 lần, 10.000 ứng viên giảm từ 56 giờ CPU xuống 7,6 phút. Throughput của 1 worker tăng từ 2,8 lên 22,3 bài/s khi chi phí khởi động được khấu hao. 10 ứng viên bệnh lý, chỉ 0,1 %, chắc chắn xuất hiện và mỗi lần gây khởi động lại REPL. Tải lệch nặng: 1 % task chậm nhất chiếm 26 % thời gian Lean, nên cần work stealing. Hàng đợi thiếu index thành điểm nghẽn trước cả Lean khi backlog lên 100.000 task. Giả thuyết H1 đúng: ở 10.000 task với 2 worker và timeout 10 giây, 45 % thời gian worker dành cho khởi động lại REPL sau timeout, kiểm chứng thật chỉ còn 46 %.

## 11. Tăng tốc đến đúng số nhân, sau đó sụp

Đường cong worker trên 10.000 task, sau khi để heartbeat làm giới hạn chính và nâng wall timeout lên 30 giây. Từ 1 lên 2 worker, throughput ổn định tăng 1,74 lần, Lean bận 94 % thời gian, không còn timeout nào: gần tuyến tính theo số nhân. Lên 4 và 8 worker trên máy 2 vCPU thì sụp xuống dưới cả 1 worker: tranh CPU làm 10 ứng viên bệnh lý vượt cả 30 giây, mỗi lần khởi động lại REPL mất 1 đến 4 phút với 4 worker, tới 5 phút với 8 worker. Từ 4 worker, trang .olean dùng chung bắt đầu bị đẩy khỏi page cache; ở 8 worker chỉ còn 1,9 GB thường trú và máy dùng tới 3 GB swap; 2 worker chết vì REPL không khởi động lại kịp, nhưng 6 worker còn lại vẫn hoàn tất đủ 10.000 kết quả, không trùng, không mất. So với giả thuyết tuần 2: hướng đúng, nhưng điểm nghẽn thật là CPU chứ không phải RAM, là cái giá khởi động lại REPL chứ không phải bản thân timeout 10 giây, và là giới hạn token đầu ra chứ không phải VRAM. Muốn nhanh hơn phải thêm máy qua Redis, không phải thêm tiến trình trên cùng một máy.

## 12. Phát hiện sai nghĩa bằng ba lớp kiểm tra

Hai ví dụ thật, đều compile được nhưng sai nghĩa. Bài GSM8K bị rút thành một phép trừ: đúng về số học nhưng không còn là bài toán. Bài MATH có giả thiết vô nghiệm trên số thực: từ a + b = 7 và a³ + b³ = 42 suy ra ab = 43/3, lớn hơn 49/4 nên không có a, b thực; mọi kết luận khi đó đều đúng một cách rỗng. Bộ kiểm tra tự động bỏ sót bài này, còn hai LLM chấm thử đều bắt được. Vì vậy hệ thống dùng ba lớp chồng nhau. Lớp 1: Lean tự kiểm tra, chạy trong cùng REPL nóng; chứng minh được là chắc chắn, chứng minh không được thì chưa nói lên điều gì. Lớp 2: heuristic rẻ về đáp án và cấu trúc phát biểu, dùng để ưu tiên. Lớp 3: người chấm trên mẫu phân tầng, độ tin cậy đo bằng Cohen's κ.

## 13. 18,7 % phát biểu compile được bị gắn cờ

Bộ kiểm tra chạy trên toàn bộ 989 phát biểu zero-shot compile được: 3.121 lệnh Lean, khoảng 26 phút với 2 worker. Màu xanh là bài Lean xác nhận được: 29 bài chứng minh được tương đương phát biểu gold, 262 bài Lean tự suy ra đáp án từ giả thiết. 185 bài, tức 18,7 %, bị gắn cờ: 143 bài MATH thiếu đáp án trong phát biểu, 40 bài GSM8K chỉ còn phép tính, 2 định lý ProofNet bị làm tầm thường. 513 bài "không thấy lỗi" là vùng tự động không kết luận được, phải nhờ người chấm. Để biết bộ kiểm tra tin được đến đâu, nhóm đo hai cách. Audit 100 mẫu: phiếu cho hai thành viên chấm đã xuất sẵn; trước đó nhóm cho hai LLM chấm độc lập để thử quy trình, κ = 0,83 cho đúng/không và 0,59 cho 3 nhãn. Mutation test: chèn lỗi cố ý vào 100 phát biểu gold; có gold thì mọi bản lỗi đều bị phát hiện, chỉ 2/100 bản đối chứng bị báo nhầm; không có gold thì đáp án sai chỉ bị bắt 26 %. Kết luận: bài có gold kiểm được bằng Lean; bài chỉ có đáp án vẫn cần người chấm hoặc dịch ngược Lean sang ngôn ngữ tự nhiên.

## 14. Giết worker giữa chừng: đủ kết quả, không trùng

Chịu lỗi. Nhóm giết một worker sau khoảng 300 kết quả. Khi cho giao lại tối đa 3 lần, cả 3 lần chạy đều đủ 1.000 kết quả, không có dòng trùng và không phải gọi lại mô hình, vì kết quả ghi bằng UPSERT theo TaskHash. Không giao lại thì 8 task vào dead-letter và mất 5 bài; retry tốn thêm khoảng 13 % thời gian. Ablation release: khi một ứng viên làm REPL quá hạn, worker trả phần còn lại của lô về hàng đợi trước khi khởi động lại REPL, nên worker kia làm tiếp ngay; makespan còn 106 giây thay vì 147 giây, ổn định qua cả 3 lần chạy mỗi bên. Ngoài ra, một sự cố thật ở 8 worker làm 2 worker chết mà vẫn đủ 10.000 kết quả; và cùng mã nguồn chạy trên Redis, một worker tham gia sau từ tiến trình độc lập làm 376 trên 1.000 task, không trùng dòng nào.

## 15. Trả lời hai câu hỏi của đề bài

Trả lời hai câu hỏi. Câu một: batching có lợi lớn ở tầng inference, gom 20 đến 26 bài mỗi request rẻ hơn 42 lần; nhưng ở tầng kiểm chứng, lô 1, 8 hay 32 task cho throughput như nhau vì thời gian nằm ở khởi động REPL và timeout. Thêm candidate nâng Pass@k lên 100 % với gấp 4 lần token mà không làm phát biểu đúng nghĩa hơn. Câu hai: compile gần như bão hoà, 98,9 %, nhưng 18,7 % phát biểu compile được bị gắn cờ sai nghĩa. Có phát biểu gold thì kiểm tra tự động bắt mọi lỗi cài sẵn; so với người chấm thử, nó chỉ bắt 58 % số phát biểu không được chấm đúng hoàn toàn và bỏ sót lỗi cần hiểu toán, nên vẫn cần người chấm. Về Big Data: ở 10.000 task, điểm nghẽn là giá của sự kiện hiếm, vì mỗi timeout kéo theo khởi động lại REPL, và số nhân CPU; muốn nhanh hơn phải thêm máy qua Redis. TaskHash, lease và UPSERT cho kết quả đúng một lần dù worker chết. Giới hạn: số audit hiện là của hai LLM chấm thử, hai thành viên còn phải chấm; máy đợt 26/10 chậm hơn đợt 16/10 nên chỉ so trong cùng đợt; con số 6 máy là ngoại suy từ một máy.

## 16. Mỗi vai trò có người chính và người dự phòng

Sáu vai trò của hướng dẫn, mỗi vai trò có một người chính và một người dự phòng có thể chạy lại và giải thích phần đó khi bảo vệ; cột Nhóm cho biết vai trò thuộc nhóm Data, System, Model hay Evaluation trên slide môn học. Bằng chứng đóng góp cá nhân là lịch sử Git, issue, pull request và nhật ký trong contributions.md. Về AI: Claude được dùng làm trợ lý lập trình và viết, nhóm giao việc theo đề bài và duyệt từng bước; Claude Haiku 5.5 là mô hình sinh mã được đánh giá; hai mô hình Claude khác chấm thử 100 mẫu audit để kiểm tra quy trình, không thay cho hai thành viên chấm. Câu hỏi trên slide môn học, ai chịu trách nhiệm nếu mô hình sinh theorem sai: là nhóm, người dùng hệ thống. Vì vậy corpus giữ kết luận và cờ ngữ nghĩa cho từng bài và không bài nào được gọi là đúng nghĩa chỉ vì Lean chấp nhận.

## 17. Cảm ơn thầy cô và các bạn đã lắng nghe

Cảm ơn và mời đặt câu hỏi. Demo theo docs/DEMO_SCRIPT.md, bảy phút. Lệnh thứ nhất chạy đúng luồng NL → Lean → checker cho một bài GSM8K: lấy ứng viên đã lưu theo TaskHash, kiểm bằng REPL Lean đã nạp sẵn Mathlib, rồi chạy bộ kiểm tra ngữ nghĩa; bài này compile được nhưng bị gắn cờ chỉ còn phép tính. Lệnh thứ hai kiểm chứng 20 bài với 2 worker và giết một worker sau 8 kết quả, để thấy lease hết hạn và task được giao lại mà không mất, không trùng. Nếu máy không có Lean, mở demo/explorer.html để duyệt 1.000 phát biểu theo nguồn, trạng thái Lean và kết luận ngữ nghĩa.
