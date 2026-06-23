#property strict
#property description "Gold short-only scalping EA with strict lot, profit lock, and loss controls."

input string TradeSymbol = "XAUUSD";
input int MagicNumber = 26062301;
input double MaxLot = 0.02;
input int MaxOpenPositions = 1;
input int SlippagePoints = 30;
input int MaxSpreadPoints = 80;

input int FastMAPeriod = 9;
input int SlowMAPeriod = 21;
input int RSIPeriod = 14;
input double SellRSIMax = 48.0;

input double LockTriggerMinUSD = 5.0;
input double LockTriggerMaxUSD = 10.0;
input double LockProfitMinUSD = 5.0;
input double LockProfitMaxUSD = 10.0;
input double HugeProfitMinUSD = 10.0;
input double HugeProfitMaxUSD = 20.0;
input int HugeProfitWindowSeconds = 180;

input double MaxLossUSD = 8.0;
input int ATRPeriod = 14;
input double ATRStopMultiplier = 1.2;
input double MinStopPoints = 120;
input int CooldownSeconds = 90;

struct TicketProfile
{
   int ticket;
   double lockTriggerUSD;
   double lockProfitUSD;
   double hugeProfitUSD;
   datetime openTime;
};

TicketProfile Profiles[32];
int ProfileCount = 0;
datetime LastCloseTime = 0;

int OnInit()
{
   MathSrand((int)GetTickCount());
   return(INIT_SUCCEEDED);
}

void OnTick()
{
   if(Symbol() != TradeSymbol)
      return;

   ManageOpenPositions();

   if(TimeCurrent() - LastCloseTime < CooldownSeconds)
      return;

   if(CountOpenPositions() >= MaxOpenPositions)
      return;

   if(CurrentSpreadPoints() > MaxSpreadPoints)
      return;

   if(ShouldOpenShort())
      OpenShortTrade();
}

bool ShouldOpenShort()
{
   double fastNow = iMA(TradeSymbol, PERIOD_M5, FastMAPeriod, 0, MODE_EMA, PRICE_CLOSE, 0);
   double fastPrev = iMA(TradeSymbol, PERIOD_M5, FastMAPeriod, 0, MODE_EMA, PRICE_CLOSE, 1);
   double slowNow = iMA(TradeSymbol, PERIOD_M5, SlowMAPeriod, 0, MODE_EMA, PRICE_CLOSE, 0);
   double slowPrev = iMA(TradeSymbol, PERIOD_M5, SlowMAPeriod, 0, MODE_EMA, PRICE_CLOSE, 1);
   double rsi = iRSI(TradeSymbol, PERIOD_M5, RSIPeriod, PRICE_CLOSE, 0);

   return(fastPrev >= slowPrev && fastNow < slowNow && rsi <= SellRSIMax);
}

void OpenShortTrade()
{
   RefreshRates();

   double lot = NormalizeLot(MaxLot);
   if(lot <= 0.0)
      return;

   double price = Bid;
   double stopLoss = BuildInitialShortStopLoss(price, lot);
   string comment = "GoldShortScalpEA";

   int ticket = OrderSend(TradeSymbol, OP_SELL, lot, price, SlippagePoints, stopLoss, 0, comment, MagicNumber, 0, clrDodgerBlue);
   if(ticket > 0)
      EnsureTicketProfile(ticket);
}

void ManageOpenPositions()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;

      if(OrderSymbol() != TradeSymbol || OrderMagicNumber() != MagicNumber)
         continue;

      int ticket = OrderTicket();
      EnsureTicketProfile(ticket);

      double profitUSD = OrderProfit() + OrderSwap() + OrderCommission();
      TicketProfile profile = GetTicketProfile(ticket);

      if(profitUSD <= -MaxLossUSD)
      {
         CloseOrder(ticket, "strict max loss");
         continue;
      }

      if(profitUSD >= profile.lockTriggerUSD)
         ApplyProfitLock(ticket, profile.lockProfitUSD);

      if(TimeCurrent() - OrderOpenTime() <= HugeProfitWindowSeconds && profitUSD >= profile.hugeProfitUSD)
      {
         CloseOrder(ticket, "huge short-term profit");
         continue;
      }
   }
}

void ApplyProfitLock(int ticket, double lockProfitUSD)
{
   if(!OrderSelect(ticket, SELECT_BY_TICKET, MODE_TRADES))
      return;

   double profitUSD = OrderProfit() + OrderSwap() + OrderCommission();
   if(profitUSD < lockProfitUSD)
      return;

   double distance = MoneyToPriceDistance(lockProfitUSD, OrderLots());
   double newStop = 0.0;
   double stopLevel = MarketInfo(TradeSymbol, MODE_STOPLEVEL) * Point;

   if(OrderType() == OP_SELL)
   {
      newStop = NormalizeDouble(OrderOpenPrice() - distance, Digits);
      if(newStop <= Ask + stopLevel)
         return;
   }
   else
      return;

   if(!ShortStopImproves(OrderStopLoss(), newStop))
      return;

   if(!OrderModify(ticket, OrderOpenPrice(), newStop, OrderTakeProfit(), 0, clrLimeGreen))
      Print("OrderModify profit lock failed. ticket=", ticket, " error=", GetLastError());
}

double BuildInitialShortStopLoss(double entryPrice, double lot)
{
   double atr = iATR(TradeSymbol, PERIOD_M5, ATRPeriod, 0);
   double atrDistance = MathMax(atr * ATRStopMultiplier, MinStopPoints * Point);
   double moneyDistance = MoneyToPriceDistance(MaxLossUSD, lot);
   double distance = MathMin(atrDistance, moneyDistance);

   return(NormalizeDouble(entryPrice + distance, Digits));
}

double MoneyToPriceDistance(double moneyUSD, double lot)
{
   double tickValue = MarketInfo(TradeSymbol, MODE_TICKVALUE);
   double tickSize = MarketInfo(TradeSymbol, MODE_TICKSIZE);

   if(tickValue <= 0.0 || tickSize <= 0.0 || lot <= 0.0)
      return(MinStopPoints * Point);

   return((moneyUSD / (tickValue * lot)) * tickSize);
}

double NormalizeLot(double requestedLot)
{
   double minLot = MarketInfo(TradeSymbol, MODE_MINLOT);
   double lotStep = MarketInfo(TradeSymbol, MODE_LOTSTEP);
   double lot = requestedLot;
   lot = MathMin(lot, MaxLot);

   if(lot < minLot)
      return(0.0);

   lot = MathFloor(lot / lotStep) * lotStep;
   return(NormalizeDouble(lot, 2));
}

int CountOpenPositions()
{
   int count = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;

      if(OrderSymbol() == TradeSymbol && OrderMagicNumber() == MagicNumber)
         count++;
   }
   return(count);
}

int CurrentSpreadPoints()
{
   return((int)MarketInfo(TradeSymbol, MODE_SPREAD));
}

bool ShortStopImproves(double oldStop, double newStop)
{
   if(oldStop <= 0.0)
      return(true);

   return(newStop < oldStop);
}

bool CloseOrder(int ticket, string reason)
{
   if(!OrderSelect(ticket, SELECT_BY_TICKET, MODE_TRADES))
      return(false);

   RefreshRates();
   double closePrice = Ask;
   bool closed = OrderClose(ticket, OrderLots(), closePrice, SlippagePoints, clrOrangeRed);

   if(closed)
   {
      LastCloseTime = TimeCurrent();
      RemoveTicketProfile(ticket);
      Print("Closed ticket=", ticket, " reason=", reason);
   }
   else
   {
      Print("OrderClose failed. ticket=", ticket, " reason=", reason, " error=", GetLastError());
   }

   return(closed);
}

void EnsureTicketProfile(int ticket)
{
   for(int i = 0; i < ProfileCount; i++)
   {
      if(Profiles[i].ticket == ticket)
         return;
   }

   if(ProfileCount >= ArraySize(Profiles))
      return;

   Profiles[ProfileCount].ticket = ticket;
   Profiles[ProfileCount].lockTriggerUSD = RandomBetween(LockTriggerMinUSD, LockTriggerMaxUSD);
   Profiles[ProfileCount].lockProfitUSD = RandomBetween(LockProfitMinUSD, LockProfitMaxUSD);
   Profiles[ProfileCount].hugeProfitUSD = RandomBetween(HugeProfitMinUSD, HugeProfitMaxUSD);
   Profiles[ProfileCount].openTime = TimeCurrent();
   ProfileCount++;
}

TicketProfile GetTicketProfile(int ticket)
{
   for(int i = 0; i < ProfileCount; i++)
   {
      if(Profiles[i].ticket == ticket)
         return(Profiles[i]);
   }

   TicketProfile fallback;
   fallback.ticket = ticket;
   fallback.lockTriggerUSD = LockTriggerMinUSD;
   fallback.lockProfitUSD = LockProfitMinUSD;
   fallback.hugeProfitUSD = HugeProfitMinUSD;
   fallback.openTime = TimeCurrent();
   return(fallback);
}

void RemoveTicketProfile(int ticket)
{
   for(int i = 0; i < ProfileCount; i++)
   {
      if(Profiles[i].ticket != ticket)
         continue;

      for(int j = i; j < ProfileCount - 1; j++)
         Profiles[j] = Profiles[j + 1];

      ProfileCount--;
      return;
   }
}

double RandomBetween(double minValue, double maxValue)
{
   if(maxValue <= minValue)
      return(minValue);

   double unit = MathRand() / 32767.0;
   return(NormalizeDouble(minValue + (maxValue - minValue) * unit, 2));
}
