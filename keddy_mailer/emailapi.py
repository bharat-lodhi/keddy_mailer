def sendEmail(email,password):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    
    me = "kingii6635@gmail.com"
    you = email
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Verification SMTP Server"
    msg['From'] = me
    msg['To'] = you
    
    html = """<html>
  					<head></head>
  					<body>
    					<h1>Keddy Mailer</h1>
    					<p>You have successfully add Server on Keddy Mailer , please click on the link below to verify</p>
    					<h2>Username : """+email+"""</h2>
    					<h2>Password : """+str(password)+"""</h2>
    					<br>
    					<a href='http://localhost:8000/verify_server?vemail="""+email+"""' >Click here to verify SMTP Server</a>		
  					</body>
				</html>
			"""
            
    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login("kingii6635@gmail.com", "anuc uccq isnm otrd")
    
    part2 = MIMEText(html, 'html')
    
    msg.attach(part2)
    
    s.sendmail(me,you, str(msg))
    s.quit()
    print("mail send successfully....")