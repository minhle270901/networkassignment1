from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
from datetime import datetime
import socket, threading, sys, traceback, os
import time

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"


def encodeing(filename):
    i = 0
    result = ""
    flag = False
    while(i < len(filename)):
        if filename[i] == '.':
            flag = True
        if flag:
            result += filename[i]

        i+=1

    return result

class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    DESCRIBE = 4


    counter = 0

    # Initiation..
    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.connectToServer()
        self.frameNbr = 0
        self.showResult = filename + "is being showned"





        # Statistics
        # variables:
        # ------------------
        self.statDataRate = 0.0 #Rate of video data received in bytes/s
        self.statTotalBytes = 0 #Total number of bytes received in a session
        self.statStartTime = 0.0 #Time in milliseconds when start is pressed
        self.statTotalPlayTime = 0.0 # Time in milliseconds of video playing since beginning
        self.statFractionLost = 0.0 # Fraction of RTP data packets from sender lost since the prev packet was sent
        self.statCumLost = 0 #Number of packets lost
        self.statExpRtpNb = 0 #Expected Sequence number of RTP messages within the session
        self.statHighSeqNb = 0 #Highest sequence number received in session



    # THIS GUI IS JUST FOR REFERENCE ONLY, STUDENTS HAVE TO CREATE THEIR OWN GUI
    def createWidgets(self):
        """Build GUI."""
        # namevid
        name = Label(self.master, text="Describe: ").grid(row=5, column=0)




        # Create describe button
        self.setup = Button(self.master, width=20, padx=3, pady=3, bg='blue')
        self.setup["text"] = "Describe"
        self.setup["command"] = self.describeMovie
        self.setup.grid(row=1, column=0, padx=2, pady=2, sticky='w')

        # Create Play button
        self.start = Button(self.master, width=20, padx=3, pady=3, bg='yellow')
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=4, column=0, padx=2, pady=2, sticky='w')

        # Create Pause button
        self.pause = Button(self.master, width=20, padx=3, pady=3, bg='red')
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=4, column=3, padx=2, pady=2)

        # Create Teardown button
        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] = self.exitClient
        self.teardown.grid(row=1, column=3, padx=2, pady=2)

        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W + E + N + S, padx=5, pady=5)



    # TODO



    def exitClient(self):
        """Teardown button handler."""
        self.sendRtspRequest(self.TEARDOWN)
        self.master.destroy()  # Close the gui window
        os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)  # Delete the cache image from video
        rate = float(self.counter / self.frameNbr)
        print('-' * 60 + "\nRTP Packet Loss Rate :" + str(rate) + "\n" + '-' * 60)
        print("time: " + str(self.statTotalPlayTime))
        print("Data rate: " + str(self.statDataRate))

    # TODO

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)

    # TODO

    def playMovie(self):
        """Play button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)  # Send SETUP request to the server
            self.statStartTime = datetime.now().time()
        elif self.state == self.READY:
            # Create a new thread to listen for RTP packets
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.statStartTime = datetime.now()
            self.sendRtspRequest(self.PLAY)
    # TODO

    def describeMovie(self):
        print("Describe Stream Button is pressed.")
        e1 = Label(self.master, text="stream: RTSP and RTP" + "and endcodding: " + encodeing(self.fileName)).grid(row=5, column=3)
        self.sendRtspRequest(self.DESCRIBE)


    def listenRtp(self):
        """Listen for RTP packets."""
        global rtpPacket
        while True:
            try:
                print("LISTENING...")
                data = self.rtpSocket.recv(20480)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)

                    curTime = datetime.now()
                    self.statTotalPlayTime = curTime - self.statStartTime
                    self.statStartTime = curTime




                    if self.frameNbr + 1 != rtpPacket.seqNum():
                        self.counter += 1
                        print('!' * 60 + "\nPACKET LOSS\n" + '!' * 60)


                    currFrameNbr = rtpPacket.seqNum()
                    print("CURRENT SEQUENCE NUM: " + str(currFrameNbr))


                    if currFrameNbr > self.frameNbr:  # Discard the late packet
                        self.frameNbr = currFrameNbr
                        self.updateMovie(self.writeFrame(rtpPacket.getPayload()))



                # compute stats

                self.statExpRtpNb += 1
                self.statHighSeqNb = rtpPacket.seqNum()
                self.statCumLost += 1
                self.statDataRate = self.statTotalBytes / (self.statTotalPlayTime.total_seconds())
                self.statFractionLost = self.statCumLost / self.statHighSeqNb
                self.statTotalBytes += len(rtpPacket.payload)#get the payload length

            except:
                # Stop listening upon requesting PAUSE or TEARDOWN
                if self.playEvent.is_set():
                    break

                # Upon receiving ACK for TEARDOWN request,
                # close the RTP socket
                if self.teardownAcked == 1:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break

    # TODO

    def writeFrame(self, data):
        """Write the received frame to a temp image file. Return the image file."""
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()

        return cachename

    # TODO

    def updateMovie(self, imageFile):
        """Update the image file as video frame in the GUI."""
        photo = ImageTk.PhotoImage(Image.open(imageFile))
        self.label.configure(image=photo, height=288)
        self.label.image = photo

    # TODO

    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except:
            tkinter.messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' % self.serverAddr)

    # TODO

    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""
        # -------------
        # TO COMPLETE
        # -------------

        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            # create thread to run RtspReply
            threading.Thread(target=self.recvRtspReply).start()

            # Update RTSP sequence number.
            self.rtspSeq += 1

            # Write the RTSP request to be sent.
            request = "%s %s %s" % ('SETUP', self.fileName, "RTSP/1.0")
            request += "\nCSeq: %d" % self.rtspSeq
            request += "\nTransport: %s; client_port= %d" % ("RTP/UDP", self.rtpPort)

            # Keep track of the sent request.
            self.requestSent = self.SETUP

        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:

            # Update RTSP sequence number.
            self.rtspSeq += 1

            # Write the RTSP request to be sent.
            request = "%s %s %s" % ('PLAY', self.fileName, "RTSP/1.0")
            request += "\nCSeq: %d" % self.rtspSeq
            request += "\nSession: %d" % self.sessionId

            # Keep track of the sent request.
            self.requestSent = self.PLAY


        # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:

            # Update RTSP sequence number.
            self.rtspSeq += 1

            request = "%s %s %s" % ('PAUSE', self.fileName, "RTSP/1.0")
            request += "\nCSeq: %d" % self.rtspSeq
            request += "\nSession: %d" % self.sessionId

            self.requestSent = self.PAUSE

        # Teardown request
        elif requestCode == self.TEARDOWN and not self.state == self.INIT:

            # Update RTSP sequence number.
            self.rtspSeq += 1

            # Write the RTSP request to be sent.
            request = "%s %s %s" % ('TEARDOWN', self.fileName, "RTSP/1.0")
            request += "\nCSeq: %d" % self.rtspSeq
            request += "\nSession: %d" % self.sessionId

            self.requestSent = self.TEARDOWN


        elif requestCode == self.DESCRIBE:
            # Update RTSP sequence number.
            self.rtspSeq += 1

            # Write the RTSP request to be sent.
            request = "%s %s %s" % ('DESCRIBE', self.fileName, "RTSP/1.0")
            request += "\nCSeq: %d" % self.rtspSeq
            request += "\nSession: %d" % self.sessionId

            self.requestSent = self.DESCRIBE

        else:
            return

        # Send the RTSP request using rtspSocket.
        self.rtspSocket.send(request.encode())

        print('\nData Sent:\n' + request)

    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while True:
            reply = self.rtspSocket.recv(1024)

            if reply:
                self.parseRtspReply(reply)

            # Close the RTSP socket upon requesting Teardown
            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
                break

    # TODO

    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.decode().split('\n')
        seqNum = int(lines[1].split(' ')[1])

        # Process only if the server reply's sequence number is the same as the request's
        if seqNum == self.rtspSeq:
            session = int(lines[2].split(' ')[1])
            # New RTSP session ID
            if self.sessionId == 0:
                self.sessionId = session

            # Process only if the session ID is the same
            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200:
                    if self.requestSent == self.SETUP:
                        # -------------
                        # TO COMPLETE
                        # -------------

                        # Update RTSP state.
                        self.state = self.READY

                        # Open RTP port.
                        self.openRtpPort()
                    elif self.requestSent == self.PLAY:
                        self.state = self.PLAYING
                    elif self.requestSent == self.PAUSE:
                        self.state = self.READY

                        # The play thread exits. A new thread is created on resume.
                        self.playEvent.set()
                    elif self.requestSent == self.TEARDOWN:
                        self.state = self.INIT

                        # Flag the teardownAcked to close the socket.
                        self.teardownAcked = 1
                # TODO

    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        # -------------
        # TO COMPLETE
        # -------------
        # Create a new datagram socket to receive RTP packets from the server
        # self.rtpSocket = ...
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Set the timeout value of the socket to 0.5sec
        # ...
        self.rtpSocket.settimeout(0.5)

        try:
            # Bind the socket to the address using the RTP port given by the client user.
            self.state = self.READY
            self.rtpSocket.bind(('', self.rtpPort))
        except:
            tkinter.messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)

    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:  # When the user presses cancel, resume playing.
            self.playMovie()
    # TODO
