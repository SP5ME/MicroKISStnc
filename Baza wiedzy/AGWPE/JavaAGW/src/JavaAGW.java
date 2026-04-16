/*******************************************************************************************
    JavaAGW.java
	A Swing based tester for the AGW Packet Transport
	authors: PKWooster, Oct 2003 GPL license
	         Michael J Pawlowsky, March 2004
	        
	Part of the R/C Pilot Project
	http://rcpilot.sourceforge.net/
	
	
*/

import javax.swing.*;
import java.awt.*;
import java.awt.event.*;
import java.nio.*;
import java.nio.charset.*;
import java.util.*;
import java.text.*;
import java.io.*;


// client class that acts as a simple terminal
public class JavaAGW extends JFrame implements PacketUser
{
	// swing GUI components
	JTextField userText = new JTextField(40);		// input text
	JTextArea log = new JTextArea(24,40);			// logging window
	JTextField statusText = new JTextField(40);		// status
	JPanel outPanel = new JPanel();
	JScrollPane logScroll = new JScrollPane(log);

	JMenuBar menuBar = new JMenuBar();
	JMenuItem startItem = new JMenuItem("Connect");
	JMenuItem hostItem = new JMenuItem("Host");
	JMenuItem discItem = new JMenuItem("Request disconnect");
	JMenuItem agwversionItem = new JMenuItem("AGWPE Version");
	JMenuItem agwMonitorItem = new JMenuItem("On AGWPE Monitor");
	JMenuItem debugItem = new JMenuItem("Debug level");
	JMenuItem aboutItem = new JMenuItem("About");
	JMenuItem exitItem = new JMenuItem("Exit");
	JMenu fileMenu = new JMenu("File");
	JMenu helpMenu = new JMenu("Help");
	private static int agw_monitor_status = 0;
	public static int debugLevel = 1;

	Container cp;

	// teminal stuff
	Controller controller;
	PacketTransport remote;			// NIO support
	String address="127.0.0.1";			// default host is self
	int port=8000;
	int sends = 1;
	public boolean readOn = true;
	int state = Packet.CLOSED;
	boolean running = false;
	Charset charset;
	CharsetEncoder encoder;
	CharsetDecoder decoder;
	StringBuffer recvBuffer;
	
	//----------------------------------------------------------------
	// only constructor is default
	JavaAGW()
	{
		controller = new Controller();	// runs the NIO select
		controller.start(true);			// start NIO select as a separate thread
		running = true;
		charset = Charset.forName("ISO-8859-1");
		decoder = charset.newDecoder();
		encoder = charset.newEncoder();
		recvBuffer = new StringBuffer();
		// build a simple GUI
		buildMenu();
		cp = getContentPane();
		log.setEditable(false);
		outPanel.add(new JLabel("Send: "));
		outPanel.add(userText);

		// enter on userText causes transmit
		userText.addActionListener(new ActionListener(){
			public void actionPerformed(ActionEvent evt){userTyped(evt);}
		});
		cp.setLayout(new BorderLayout());
		cp.add(outPanel,BorderLayout.NORTH);
		cp.add(logScroll,BorderLayout.CENTER);
		cp.add(statusText,BorderLayout.SOUTH);
		setStatus("Closed");
		addWindowListener(new WindowAdapter()
		{public void windowClosing(WindowEvent evt){mnuExit();}});

		// put some documentaion in log window
		toLog("!! use start menu to start");
		toLog("!! host is "+address+":"+port);
		pack();
	}

	// user pressed enter in the user text field, we try to send the text
	void userTyped(ActionEvent evt)
	{
		String txt = evt.getActionCommand();
		userText.setText("");	// don't send it twice
		toLog(txt, true);
		System.out.println("From user:"+txt);

		// put the text on the remote transmit queue
		if(state == Packet.OPENED)
		for(int i = 0; i<sends; i++)sendText(txt);
	}

	// methods to put text in logging window, toLog(text,true) if it came from user
	void toLog(String txt){toLog (txt,false);}
	void toLog(String txt, boolean user)
	{
		log.append((user?"> ":"< ")+txt+"\n");
		log.setCaretPosition(log.getDocument().getLength() ); // force last line visible
	}


	// build the standard menu bar
	void buildMenu()
	{
		JMenuItem item;

		// file menu
		startItem.addActionListener(new ActionListener()
		{public void actionPerformed(ActionEvent e){mnuStart();}});
		fileMenu.add(startItem);

		hostItem.addActionListener(new ActionListener()
		{public void actionPerformed(ActionEvent e){mnuHost();}});
		fileMenu.add(hostItem);
		
		agwversionItem.addActionListener(new ActionListener()
		{public void actionPerformed(ActionEvent e){getAGWVersion();}});
		fileMenu.add(agwversionItem);
		
		agwMonitorItem.addActionListener(new ActionListener()
		{public void actionPerformed(ActionEvent e){monitorAGW();}});
		fileMenu.add(agwMonitorItem);				

		discItem.addActionListener(new ActionListener()
		{public void actionPerformed(ActionEvent e){mnuDisc();}});
		fileMenu.add(discItem);

		debugItem.addActionListener(new ActionListener()
		{public void actionPerformed(ActionEvent e){mnuDebug();}});
		fileMenu.add(debugItem);

		exitItem.addActionListener(new ActionListener()
		{public void actionPerformed(ActionEvent e){mnuExit();}});
		fileMenu.add(exitItem);
		menuBar.add(fileMenu);


		helpMenu.add(aboutItem);
		aboutItem.addActionListener(new ActionListener()
		{public void actionPerformed(ActionEvent e){mnuAbout();}});

		menuBar.add(helpMenu);

		setJMenuBar(menuBar);
	}



	// start and stop menu
	void mnuStart()
	{
		switch(state)
		{
			case Packet.CLOSED:
				remote = new PacketTransport(controller);
				if(remote.connect(this,address,port))setSockState (Packet.OPENING);
				else remote = null;
				break;
			case Packet.OPENED:
			case Packet.OPENING:
			case Packet.CLOSING:
				if(remote != null)remote.disconnect();	// shut it down
				break;
		}
	}

	// prompt user for host in form address:port
	// default is 127.0.0.1:8000
	void mnuHost()
	{
		String txt = JOptionPane.showInputDialog("Enter host address and port");
		if (txt == null)return;

		int n = txt.indexOf(':');
		if(n == 0)
		{
			address = "127.0.0.1";
			port = Functions.toInt(txt.substring(1),8000);
		}
		else if(n < 0)
		{
			address = txt;
			port = 8000;
		}
		else
		{
			address = txt.substring(0,n);
			port = Functions.toInt(txt.substring(n+1),8000);
		}
			toLog("!! host set to "+address+":"+port);
	}
	
	
	
	void getAGWVersion(){
		toLog("send version request");
		Packet pkt = new Packet(this, Packet.SEND, null, null); // get an empty send packet
		pkt.setDataKind((int)'R');	// set the type
		pkt.setPort(0);
		pkt.setCallTo(null);
		pkt.setCallFrom(null);
		try {
			remote.send(pkt);
		} catch(Exception e){
			toLog(e.toString());
			toLog("Did you connect?");
		}

	}
	
	
	void monitorAGW(){
		toLog("send monitor request");
		Packet pkt = new Packet(this, Packet.SEND, null, null); // get an empty send packet
		pkt.setDataKind((int)'m');	// set the type
		pkt.setPort(0);
		pkt.setCallTo(null);
		pkt.setCallFrom(null);
		try {
			remote.send(pkt);
			if (agw_monitor_status == 0){
				agw_monitor_status = 1;
				agwMonitorItem.setText("Off AGWPE Monitor");
			} else {
				agwMonitorItem.setText("On AGWPE Monitor");
				agw_monitor_status = 0;
			}
		}catch(Exception e){
			toLog(e.toString());
			toLog("Did you connect?");
		}
	}
	
	
	void mnuDisc()
	{
		if(state == Packet.OPENED)
		{
			remote.disconnect();    // request disconnect
			setSockState (Packet.CLOSING);
		}
	}


	void mnuDebug()
	{
		String txt = JOptionPane.showInputDialog("Enter debug level");
		if (txt == null)return;
		Functions.setDebugLevel(Functions.toInt(txt,0));
	}

	void mnuAbout(){new AboutDialog(this).setVisible(true);}

	// exit menu
	void mnuExit()
	{
		System.exit(0);
	}

	private void sendText(String txt)
	{
		toLog("send requested");
		txt += "\n...";
		ByteBuffer buf = encode(txt);	// encode chars as bytes
		System.out.println("sendText buffer position="+buf.position()+" limit="+buf.limit());	
		Packet pkt = new  Packet(this,Packet.SEND,null,buf);
		remote.send(pkt);
	}

	// encode a string using our character encoder
	private ByteBuffer encode(String str)
	{
		ByteBuffer buffer=null;
		CharBuffer cb = CharBuffer.wrap(str);
		System.out.println("encode str len="+str.length()+" cb position="+cb.position()+" limit="+cb.limit());
		try{buffer = encoder.encode(cb);}
		catch(Exception e){e.printStackTrace();}
		System.out.println("encoded buffer position="+buffer.position()+" limit="+buffer.limit());
		return buffer;
	}
	
	
	private void receive(Packet pkt)
	{
		
		toLog("received packet data length="+pkt.getDataLength());
		
		ByteBuffer hbuffer = pkt.getHeader();
		Functions.println("header position="+hbuffer.position()+" limit="+hbuffer.limit()+" remaining="+hbuffer.remaining());
			
		ByteBuffer buffer = pkt.getData();
		Functions.println("received position="+buffer.position()+" limit="+buffer.limit()+" remaining="+buffer.remaining());
		
		toLog("Header", true);
		int hlen = hbuffer.limit();
		byte[] head = new byte[hlen];
		hbuffer.get(head,0,hlen);
		toLogHex(head,0,hlen);
		
		toLog("Data", true);
		int dlen = buffer.limit();
		byte[] dat = new byte[dlen];
		buffer.get(dat,0,dlen);
		toLogHex(dat,0,dlen);		
	}
	
/**
 * print the hexadecimal and character representation of a byte array
 * @param ba the byte array
 * @param ofs the offset to start at
 * @param len the length to print
 */
	public void toLogHex(byte[]ba, int ofs, int len)
	{
		int dlen;
		String dstr;

		while(len>0)
		{
			if(len < 16)
			{
				dlen = len;
				char[] c48 = new char[48];
				Arrays.fill(c48, ' ');
				String fill48 = String.valueOf(c48);
				dstr = fill48.substring(0,3*(16-dlen));
			}
			else
			{
				dlen = 16;
				dstr = "";
			}
			dstr = Functions.tohex4(ofs)+": "+Functions.atohex(ba,ofs,dlen)+dstr+": "+Functions.atochar(ba,ofs,dlen);
			toLog(dstr, true);
			ofs+=dlen;
			len-=dlen;
		}

	}	
	
	
	private void setSockState (int s)
	{
		if(state != s)
		{
			state = s;
			switch(state)
			{
				case Packet.OPENED:
					startItem.setText("Disconnect");
					setStatus("Connected to "+address);
					break;
				case Packet.CLOSED:
					startItem.setText("Connect");
					agwMonitorItem.setText("On AGWPE Monitor");
					agw_monitor_status = 0;
					setStatus("Disconnected");
					remote = null;
					if(!running)System.exit(0);
					break;
				case Packet.OPENING:
					setStatus("Connecting to "+address);
					startItem.setText("Abort");
					break;

				case Packet.CLOSING:
					setStatus("Disconnecting from "+address);
					startItem.setText("Abort");
					break;
			}
		}
	}

	void setStatus(String st)
	{
		statusText.setText(st);
	}

	// called when the run method in Packet is executed in the AWT event dispatch thread
	// looks a bit like an action event
	public void runPacket(Packet pkt)
	{
		int type = pkt.getType();
		
		switch(type)
		{
			case Packet.STATE:
				int s = ((Integer)pkt.getArg()).intValue();
				setSockState(s);
				break;

			case Packet.RECEIVE:
				receive(pkt);  
				break;
				
			case Packet.FLOW:
				boolean b = ((Boolean)pkt.getArg()).booleanValue();
				toLog("flow="+b);
				break;
			default:
				toLog("unexpected packet type="+type);
				break;	
		}
	}

	// uses invokeLater to put this packet on the system event queue so Swing will run it
	public void postPacket(Packet pkt)
	{
		SwingUtilities.invokeLater(pkt);	// the packet implements Runnable, so we can use invokeLater
	}

	// start up
	static public void main(String[] args)
	{
		new JavaAGW().setVisible(true);
	}
	

	

	//============================================================================================
	// inner classes

	//----------------------------------------------------------------------------
	// about dialog
	class AboutDialog extends JDialog
	{
		Container contentPane;
		JTextField text = new JTextField("Part of the R/C Pilot Project. http://rcpilot.sourceforge.net/");

		AboutDialog(Frame f)
		{
			super(f,"About Client",true);
			contentPane = getContentPane();
			contentPane.add(text);
			pack();
		}
	}
}